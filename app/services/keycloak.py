import json
from keycloak import KeycloakAdmin, KeycloakOpenID
from keycloak.exceptions import KeycloakAuthenticationError
import logging
import os
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError, ExpiredSignatureError
from ..config import settings
from .. import schemas
from ..cache import cache
from dotenv import load_dotenv
from typing import Annotated
import httpx
import time


load_dotenv()
logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.keycloak_server_url}realms/{settings.keycloak_realm}/protocol/openid-connect/token")
ALGORITHMS = ["RS256"]
PUBLIC_KEY = settings.keycloak_public_key
AUDIENCE = "account"
# settings.keycloak_client_id
ISSUER = f'{settings.keycloak_server_url}/realms/{settings.keycloak_realm}'


class KeycloakService:
    _jwks_cache = None
    _jwks_cache_time = None
    _jwks_cache_ttl = 3600  # 1 hour cache for JWKS
    _http_client = None
    
    def __init__(self):
        self.server_url = settings.keycloak_server_url
        self.realm = settings.keycloak_realm
        self.client_id = settings.keycloak_client_id
        self.client_secret = settings.keycloak_client_secret
        self.token_url = f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/token"
        self.jwks_url = f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/certs"
        self.issuer = f"{settings.keycloak_server_url}/realms/{settings.keycloak_realm}"
        self.audience = "account"
        
        # Initialize admin client lazily to avoid blocking startup
        self._keycloak_admin = None
        self._keycloak_openid = None
    
    @property
    def keycloak_admin(self):
        if self._keycloak_admin is None:
            self._keycloak_admin = KeycloakAdmin(
                server_url=self.server_url,
                username=settings.keycloak_admin_username,
                password=settings.keycloak_admin_password,
                realm_name=self.realm,
                user_realm_name="master",
                client_id="admin-cli",
                verify=True
            )
        return self._keycloak_admin
    
    @property
    def keycloak_openid(self):
        if self._keycloak_openid is None:
            self._keycloak_openid = KeycloakOpenID(
                server_url=self.server_url,
                client_id=self.client_id,
                realm_name=self.realm,
                client_secret_key=self.client_secret,
                verify=True
            )
        return self._keycloak_openid
    
    @classmethod
    async def get_http_client(cls):
        if cls._http_client is None:
            timeout = httpx.Timeout(10.0, connect=5.0)
            limits = httpx.Limits(max_keepalive_connections=20, max_connections=100)
            cls._http_client = httpx.AsyncClient(timeout=timeout, limits=limits)
        return cls._http_client
    
    @classmethod
    async def close_http_client(cls):
        if cls._http_client:
            await cls._http_client.aclose()
            cls._http_client = None

    async def create_user_async(self, email: str, username: str, password: str, first_name: str, last_name: str, role: str| None = None) -> str:
        """
        Create a user in Keycloak asynchronously @ role is optional and will be added on to realm roles if provided
        """
        try:
            payload ={
                "email": email,
                "username": username,
                "firstName": first_name,
                "lastName": last_name,
                "enabled": True,
                "emailVerified": True,
                "credentials": [{"type": "password", "value": password, "temporary": False}]
            }
            if role: 
                payload["realmRoles"] = [role]

            new_user = await self.keycloak_admin.a_create_user(payload, exist_ok=False)

            logger.info(f"User created in Keycloak: {new_user}")

            if isinstance(new_user, str):  # Keycloak might return the ID as a string
                return new_user
            elif isinstance(new_user, dict) and 'id' in new_user:
                return new_user['id']
            else:
                logger.error(f"Unexpected response from Keycloak: {new_user}")
                raise HTTPException(
                    status_code=500,
                    detail="Unexpected response from Keycloak during user creation"
                )
        except KeycloakAuthenticationError as e:
            logger.error(f"Keycloak authentication error: {e}")
            raise HTTPException(
                status_code=400,
                detail="Failed to authenticate with Keycloak"
            )
        except Exception as e:
            logger.error(
                f"Unexpected error during Keycloak user creation: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user in Keycloak"
            )
            
    async def create_user(self, email: str, username: str, password: str, first_name: str, last_name: str, role: str) -> str:
        try:
            new_user = self.keycloak_admin.create_user({
                "email": email,
                "username": username,
                "firstName": first_name,
                "lastName": last_name,
                "enabled": True,
                "emailVerified": True,
                "credentials":  [{"type": "password", "value": password, "temporary": False}],
                "realmRoles": [role]
            })
            logger.info(f"User created in Keycloak with ID: {new_user}")
            return new_user
        except KeycloakAuthenticationError as e:
            logger.error(f"Keycloak Authentication error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication server error"
            ) from e
        except Exception as e:
            logger.error(f"Keycloak user creation failed {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user in authentication service"
            ) from e

    async def delete_user(self, keycloak_id: str):
        try:
            self.keycloak_admin.delete_user(keycloak_id)
            logger.info(
                "User with keycloak ID {keycloak_id} deleted from keycloak")
        except KeycloakAuthenticationError as e:
            logger.error(f"Keycloak authentication error: {e}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Failed to delete user from authentication service"
                                ) from e
        except Exception as e:
            logger.error(f"Keycloak user deletion failed {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service error",
            ) from e

    async def _get_jwks_cached(self) -> dict:
        """Get JWKS with Redis caching to avoid repeated requests"""
        cache_key = f"jwks:{self.realm}"
        
        # Try to get from Redis cache first
        jwks = await cache.get(cache_key)
        if jwks:
            return jwks
        
        # Fetch new JWKS
        try:
            client = await self.get_http_client()
            response = await client.get(self.jwks_url)
            response.raise_for_status()
            jwks = response.json()
            
            # Cache for 1 hour
            await cache.set(cache_key, jwks, ttl=3600)
            
            return jwks
        except httpx.HTTPError:
            logger.error(f"JWKS endpoint error, using fallback")
            # Try in-memory cache as fallback
            current_time = time.time()
            if (self._jwks_cache is not None and 
                self._jwks_cache_time is not None and 
                current_time - self._jwks_cache_time < self._jwks_cache_ttl):
                logger.warning("Using stale in-memory JWKS cache")
                return self._jwks_cache
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable",
            )
    
    async def decode_token(self, token: str) -> 'schemas.Claims':
        """
        Decode and validate JWT token using cached Keycloak public keys
        """
        try:
            # Check if we've already decoded this token recently
            token_hash = str(hash(token))[-8:]  # Use last 8 chars of hash
            cache_key = f"token:{token_hash}"
            cached_claims = await cache.get(cache_key)
            if cached_claims:
                return schemas.Claims(**cached_claims)
            
            # Get JWKS with caching
            jwks = await self._get_jwks_cached()
            
            # Decode JWT header
            unverified_header = jwt.get_unverified_header(token)
            
            # Find the key with the matching kid
            rsa_key = {}
            for key in jwks.get('keys', []):
                if key.get('kid') == unverified_header.get('kid'):
                    rsa_key = {
                        'kty': key.get('kty'),
                        'kid': key.get('kid'),
                        'use': key.get('use'),
                        'n': key.get('n'),
                        'e': key.get('e')
                    }
                    break
            
            if not rsa_key:
                logger.error("Unable to find appropriate key in JWKS")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Decode and validate token
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=ALGORITHMS,
                audience=self.audience,
                issuer=self.issuer
            )
            
            roles = payload.get('realm_access', {}).get('roles', [])
            
            # Map payload to Claims schema
            claims = schemas.Claims(
                id=payload['sub'],
                email=payload.get('email', ''),
                name=payload.get('name', ''),
                preferred_username=payload.get('preferred_username', ''),
                given_name=payload.get('given_name', ''),
                family_name=payload.get('family_name', ''),
                roles=roles,
                exp=payload['exp'],
                iat=payload['iat'],
                iss=payload['iss'],
                aud=payload['aud']
            )
            
            # Cache the decoded claims for 5 minutes
            await cache.set(cache_key, claims.dict(), ttl=300)
            
            return claims
            
        except ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except httpx.HTTPError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable",
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )

    async def get_user_by_email(self, email: str):
        try:
            users = self.keycloak_admin.get_users({
                "email": email
            })
            if users:
                return users[0]
            return None
        except KeycloakAuthenticationError as e:
            raise Exception(f"Failed to get user from keycloak: {e}")

    async def authenticate_user(self, username: str, password: str) -> dict:
        """Authenticate user with Keycloak using persistent connection"""
        try:
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'password',
                'username': username,
                'password': password,
                'scope': 'openid'
            }
            
            client = await self.get_http_client()
            response = await client.post(self.token_url, data=data)
            response.raise_for_status()
            tokens = response.json()
            
            return tokens
            
        except httpx.HTTPError as e:
            logger.error(f"Authentication failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

    async def logout(self, refresh_token: str) -> bool:
        """Logout user from Keycloak"""
        try:
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': refresh_token
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/logout",
                    data=data
                )
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Logout failed"
            )

    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh access token"""
        try:
            data = {
                'grant_type': 'refresh_token',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': refresh_token
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(self.token_url, data=data)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Token refresh failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

    async def reset_password(self, keycloak_id: str, new_password: str):
        """
        Reset the user's password in Keycloak.
        """
        try:
            self.keycloak_admin.update_user(
                user_id=keycloak_id,
                payload={
                    "credentials": [
                        {
                            "type": "password",
                            "value": new_password,
                            "temporary": False
                        }
                    ]
                }
            )
            logger.info(
                f"Password reset successfully for Keycloak ID: {keycloak_id}")
        except KeycloakAuthenticationError as e:
            logger.error(f"Keycloak authentication error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reset password in Keycloak"
            )
        except Exception as e:
            logger.error(
                f"Unexpected error during Keycloak password reset: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while resetting the password in Keycloak"
            )

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange authorization code for tokens"""
        try:
            data = {
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': redirect_uri,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/token",
                    data=data
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Code exchange failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange code for token"
            )

    async def get_user_info(self, access_token: str) -> dict:
        """Get user info from Keycloak Using Access token from the userinfo endpoint"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}'
            }
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/userinfo",
                    headers=headers
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get user info"
            )

    async def get_user_roles(self, keycloak_id: str) -> list:
        """Get user roles from Keycloak"""
        try:
            user = self.keycloak_admin.get_user(keycloak_id)
            if user:
                return user.get('realm_roles', [])
            return []
        except Exception as e:
            logger.error(f"Failed to get user roles: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get user roles"
            )

    async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
        """
        Validate the Bearer token and retreive the current user.
        """
        user = await KeycloakService.decode_token(token)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    async def get_current_superuser(current_user: schemas.User = Depends(get_current_user)) -> schemas.User:
        """
        Ensure the user is a superuser.
        """
        if current_user.role != "superuser":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user

    async def get_current_admin(current_user: schemas.User = Depends(get_current_user)) -> schemas.User:
        """
        Ensure the user is an admin.
        """
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user

    async def get_current_staff(current_user: schemas.User = Depends(get_current_user)) -> schemas.User:
        """
        Ensure the user is a staff member.
        """
        if current_user.role != "staff":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user

    async def get_current_user_from_keycloak(token: str = Depends(oauth2_scheme)) -> schemas.User:
        """
        Validate the Bearer token and retrieve the current user from Keycloak.
        """
        try:
            claims = await KeycloakService.decode_token(token)
            logger.info(f"Decoded token: {claims}")
            user = schemas.User(
                user_id=claims.id,
                keycloak_id=claims.id,
                email=claims.email,
                username=claims.preferred_username,
                first_name=claims.given_name,
                last_name=claims.family_name,
                role=claims.roles[0] if claims.roles else "User"
            )
            return user
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    async def get_current_user_from_keycloak_with_role(token: str = Depends(oauth2_scheme), role: str = "User") -> schemas.User:
        """
        Validate the Bearer token and retrieve the current user from Keycloak with a specific role.
        """
        try:
            claims = await KeycloakService.decode_token(token)
            logger.info(f"Decoded token: {claims}")
            user = schemas.User(
                user_id=claims.id,
                keycloak_id=claims.id,
                email=claims.email,
                username=claims.preferred_username,
                first_name=claims.given_name,
                last_name=claims.family_name,
                role=role
            )
            return user
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

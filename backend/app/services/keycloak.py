import json
from keycloak import KeycloakAdmin, KeycloakOpenID
from keycloak.exceptions import KeycloakAuthenticationError
import logging
import os
import requests
from fastapi import HTTPException, status
from jose import jwt, JWTError
# from fastapi.security import OAuth2PasswordBearer
from ..config import settings
from .. import models, schemas
from dotenv import load_dotenv
import httpx


load_dotenv()
logger = logging.getLogger(__name__)


class KeycloakService:
    def __init__(self):
        self.server_url = settings.keycloak_server_url
        self.realm = settings.keycloak_realm
        self.client_id = settings.keycloak_client_id
        self.client_secret = settings.keycloak_client_secret
        self.token_url = f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/token"
        # Initialize jwks_url
        self.jwks_url = f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/certs"
        self.keycloak_admin = KeycloakAdmin(
            server_url=self.server_url,
            username=settings.keycloak_admin_username,
            password=settings.keycloak_admin_password,
            realm_name=self.realm,
            user_realm_name="master",
            client_id="admin-cli",
            verify=True
        )
        self.keycloak_openid = KeycloakOpenID(
            server_url=self.server_url,
            client_id=self.client_id,
            realm_name=self.realm,
            client_secret_key=self.client_secret,
            verify=True
        )

    def create_user(self, email: str, username: str, password: str, first_name: str, last_name: str, role: str) -> str:
        try:
            user_id = self.keycloak_admin.create_user({
                "email": email,
                "username": username,
                "firstName": first_name,
                "lastName": last_name,
                "enabled": True,
                "emailVerified": True,
                "credentials":  [{"type": "password", "value": password, "temporary": False}],
                "realmRoles": [role]
            })
            logger.info(f"User created in Keycloak with ID: {user_id}")
            return user_id
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

    def delete_user(self, keycloak_id: str):
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

    def decode_token(self, token: str) -> 'schemas.Claims':
        """
        Decode and validate JWT token using Keycloak's public keys
        """

        try:

            jwks_response = requests.get(self.jwks_url)
            jwks_response.raise_for_status()
            jwks = jwks_response.json()

            # Decode JWT header
            unverified_header = jwt.get_unverified_header(token)
            logger.debug(f"Unverified JWT header: {unverified_header}")

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

                # decode and validate token
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                audience=settings.keycloak_client_id,
                issuer=f"{self.server_url}/realms/{self.realm}"
            )
            logger.debug(f"Decoded JWT payload: {payload}")

            roles = payload.get('realm_access', {}).get('roles', [])

            logger.debug(f"Extracted roles: {roles}")

            # Map claims to pydantic claims model
            # c  # Map payload to Claims schema
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
            logger.info(f"Claims extracted successfully for user {
                        claims.email}")
            return claims
        except JWTError as e:
            logger.error(f"Token decoding failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except requests.HTTPError as e:
            logger.error(f"JWKS endpoint error: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable",
            )
        except Exception as e:
            logger.error(f"Unexpected error during token decoding: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )

    def get_user_by_email(self, email: str):
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
        """Authenticate user with Keycloak"""
        try:
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'password',
                'username': username,
                'password': password,
                'scope': 'openid'  # Add this to get id_token
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(self.token_url, data=data)
                response.raise_for_status()
                tokens = response.json()

                # Provide default values if tokens are missing
                return {
                    "access_token": tokens["access_token"],
                    "refresh_token": tokens["refresh_token"],
                    # Default to empty string if missing
                    "id_token": tokens.get("id_token", ""),
                    "expires_in": tokens.get("expires_in", 300),
                    "refresh_expires_in": tokens.get("refresh_expires_in", 1800),
                    "token_type": tokens.get("token_type", "Bearer")
                }

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

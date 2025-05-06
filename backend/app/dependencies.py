# app/dependencies.py


from fastapi import Depends, HTTPException, status, Header, Cookie
from fastapi.security import OAuth2AuthorizationCodeBearer, OAuth2PasswordBearer
from keycloak import KeycloakAdmin, KeycloakOpenID
from typing import List, Optional, Annotated
import logging
from jose import JWTError, jwt
from jwt import PyJWKClient
from . import schemas
from .config import settings
from .schemas import User
from .services.keycloak import KeycloakService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.keycloak_server_url}realms/{settings.keycloak_realm}/protocol/openid-connect/token")

keycloak_admin = KeycloakAdmin(
    server_url=settings.keycloak_server_url,
    username=settings.keycloak_admin_username,
    password=settings.keycloak_admin_password,
    realm_name=settings.keycloak_realm,
    client_id=settings.keycloak_client_id,
    client_secret_key=settings.keycloak_client_secret,
    verify=True
)
keycloak_openid = KeycloakOpenID(
    server_url=settings.keycloak_server_url,
    client_id=settings.keycloak_client_id,
    realm_name=settings.keycloak_realm,
    client_secret_key=settings.keycloak_client_secret,
    verify=True
)
logger = logging.getLogger(__name__)
keycloak_service = KeycloakService()

def decode_token(token: str) -> User:   
   try:
        # Decode and validate the token using KeycloakService
        claims = keycloak_service.decode_token(token)
        logger.info(f"Decoded token: {claims}")

        # Map the claims to the User schema
        user = User(
            user_id=claims.id,
            keycloak_id=claims.id,
            email=claims.email,
            username=claims.preferred_username,
            first_name=claims.given_name,
            last_name=claims.family_name,
            role=claims.roles[0] if claims.roles else "User"
        )
        return user 
   except HTTPException as e:
        logger.error(f"Token validation failed: {e.detail}")
        raise e

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    """
    Validate the Bearer token and retreive the current user.
    """
    user = decode_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Ensure the user is active.
    """
    if current_user.role != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    return current_user


async def get_current_superuser(current_user: User = Depends(get_current_user)) -> User:
    """
    Ensure the user is a superuser.
    """
    if current_user.role != "superuser":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Ensure the user is an admin.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


async def get_current_staff(current_user: User = Depends(get_current_user)) -> User:
    """
    Ensure the user is a staff member.
    """
    if current_user.role != "staff":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


async def get_current_user_from_keycloak(token: str = Depends(oauth2_scheme)) -> User:
    """
    Validate the Bearer token and retrieve the current user from Keycloak.
    """
    try:
        claims = keycloak_service.decode_token(token)
        logger.info(f"Decoded token: {claims}")
        user = User(
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


async def get_current_user_from_keycloak_with_role(token: str = Depends(oauth2_scheme), role: str = "User") -> User:
    """
    Validate the Bearer token and retrieve the current user from Keycloak with a specific role.
    """
    try:
        claims = keycloak_service.decode_token(token)
        logger.info(f"Decoded token: {claims}")
        user = User(
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


async def get_current_user_from_cookies(
    access_token: str = Cookie(None),
    csrf_token: str = Header(None),
    csrf_cookie: str = Cookie(None)
) -> User:
    """
    Validate the Bearer token stored in cookies and retrieve the current user.
    """
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate CSRF token
    if csrf_token != csrf_cookie:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )

    try:
        # Decode and validate the token using KeycloakService
        claims = keycloak_service.decode_token(access_token)
        logger.info(f"Decoded token: {claims}")

        # Map the claims to the User schema
        user = User(
            user_id=claims.id,
            keycloak_id=claims.id,
            email=claims.email,
            username=claims.preferred_username,
            first_name=claims.given_name,
            last_name=claims.family_name,
            role=claims.roles[0] if claims.roles else "User"
        )
        return user
    except HTTPException as e:
        logger.error(f"Token validation failed: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during token validation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during token validation",
        )


def validate_csrf(csrf_token: Optional[str] = Header(None), csrf_cookie: Optional[str] = Cookie(None)):
    """
    Validates that the CSRF token sent in headers matches the one stored in cookies.
    """
    if not csrf_token or not csrf_cookie:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing",
        )
    if csrf_token != csrf_cookie:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )
    return True


async def valid_access_token(
    access_token: Annotated[str, Depends(oauth2_scheme)]
):
    url = f"{settings.keycloak_server_url}realms/{settings.keycloak_realm}/protocol/openid-connect/certs"
    optional_custom_headers = {"User-agent": "custom-user-agent"}
    jwks_client = PyJWKClient(url, headers=optional_custom_headers)

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(access_token)
        data = jwt.decode(
            access_token,
            signing_key.key,
            algorithms=["RS256"],
            audience="api",
            options={"verify_exp": True},
        )
        return data
    except JWTError as e:
        logger.error(f"JWT Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )   


def require_roles(required_roles: List[str]):
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker

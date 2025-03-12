# app/dependencies.py


from fastapi import Depends, HTTPException, status, Header, Cookie
from fastapi.security import OAuth2PasswordBearer
from typing import List, Optional
import logging
from jose import JWTError, jwt
from . import schemas
from .schemas import User
from .services.keycloak import KeycloakService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

logger = logging.getLogger(__name__)
keycloak_service = KeycloakService()


async def get_current_user(
    access_token: Optional[str] = Cookie(None),
    refresh_token:Optional[str] = Cookie(None),
    id_token: Optional[str] = Cookie(None)
    ) -> schemas.User:
    """
    Retrieve the current user from the Authorization header (Bearer token).
    """
    if not access_token:
        logger.warning("Access token missing in cookies ")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = keycloak_service.decode_token(access_token)
        user = schemas.User(
            user_id=claims.id,
            keycloak_id=claims.get("sub"),
            email=claims.get("email"),
            username=claims.get(
                "preferred_username") or claims.get("name") or "",
            first_name=claims.get("given_name") or "",
            last_name=claims.get("family_name") or "",
            role=claims.get("roles")[0] if claims.get("roles") else "User"
        )
        logger.info(
            f"Authenticated user: {user.username} with role: {user.role}")  
        return user 
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error decoding token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e 


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


def require_roles(required_roles: List[str]):
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker

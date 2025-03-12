# app/routers/auth.py
from fastapi import APIRouter,  HTTPException, Depends, status, Request, Response
from fastapi.responses import RedirectResponse
# from passlib.context import CryptContext
# from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
# from starlette.middleware.sessions import SessionMiddleware
# from keycloak import KeycloakOpenID
# from sqlalchemy.orm import Session
import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError

from ..utils.utils import hash_password
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db
from ..services.keycloak import KeycloakService
import requests
import httpx
# import bcrypt
import secrets
import logging
# from ..database import get_db
# from ..models import User

from typing import Optional


from ..config import settings

# Initialize bcrypt password context
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Create Keycloak client and setup constants
logger = logging.getLogger(__name__)


# Configure JWT settings
ALGORITHMS = ["RS256"]
PUBLIC_KEY = settings.keycloak_public_key
AUDIENCE = settings.keycloak_client_id
ISSUER = f'{settings.keycloak_server_url}/realms/{settings.keycloak_realm}'


router = APIRouter(prefix="/auth", tags=["auth"])


def get_public_key():
    """Retreive the public key dynamically from keycloak."""
    url = f'{ISSUER}/protocol/openid-connect/certs'
    jwks_client = PyJWKClient(url)
    return jwks_client
    # response = requests.get(url)
    # realm_info = response.json()
    # public_key = realm_info['public_key']
    # return f"-----BEGIN PUBLIC KEY-----\n{public_key}\n-----END PUBLIC KEY-----"


async def validate_access_token(access_token: str):
    jwks_url = f"{settings['keycloak_server_url']}/realms/{settings['keycloak_realm']}/protocol/openid-connect/certs"
    jwks_client = PyJWKClient(jwks_url)
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(access_token)
        data = jwt.decode(
            access_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings["keycloak_client_id"],
            options={"verify_exp": True},
        )
        return data
    except jwt.exceptions.InvalidTokenError as e:
        logger.error(f"Token validation failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")


keycloak_service = KeycloakService()


@router.post("/signup", response_model=schemas.SignupResponse)
async def signup(signup_req: schemas.SignupRequest, db: Session = Depends(get_db)):

    logger.info(f"Attempting to sign up user: {signup_req.username}")

    # Check if user already exists
    existing_user = db.query(models.User).filter(
        (models.User.email == signup_req.email) |
        (models.User.username == signup_req.username)
    ).first()
    if existing_user:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or Username already registered"
        )
    try:
        # Create user in Keycloak
        keycloak_user_id = keycloak_service.create_user(
            email=signup_req.email,
            username=signup_req.username,
            password=signup_req.password,
            first_name=signup_req.first_name,
            last_name=signup_req.last_name,
            role=signup_req.role.upper()
        )
        logger.info(f"User created in keycloak with ID: {keycloak_user_id}")
    except Exception as e:
        logger.error(f"Keycloak user creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user in authentication service"
        )

    # Hash the password before saving local
    hashed_pw = hash_password(signup_req.password)

    # Retreive the role id based on the role name
    role = db.query(models.Role).filter(
        models.Role.name == signup_req.role).first()
    if not role:
        logger.error(f"Role '{signup_req.role}' not found in the database.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role specified"
        )

    # Create user in local DB
    user = models.User(
        keycloak_id=keycloak_user_id,
        email=signup_req.email,
        username=signup_req.username,
        password_hash=hashed_pw,
        first_name=signup_req.first_name,
        last_name=signup_req.last_name,
        role_id=role.id
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"User {user.username} created succesfully with ID {
                user.user_id}.")

    return schemas.SignupResponse(
        user_id=user.user_id,
        keycloak_id=user.keycloak_id,
        email=user.email,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        role=role.name,
        message=f"User {user.username} ws created succesfully!"
    )


@router.post("/login", response_model=schemas.LoginResponse)
async def login(login_req: schemas.LoginRequest, response: Response):
    try:
        tokens = await keycloak_service.authenticate_user(
            login_req.username, login_req.password)

        csrf_token = secrets.token_hex(16)

        # Set cookies for the tokens we have
        if tokens.get("access_token"):
            response.set_cookie(
                key="access_token",
                value=tokens["access_token"],
                httponly=True,
                secure=False,  # Set to True in production
                samesite='Lax',
                max_age=tokens.get("expires_in", 300),
                path="/",
                domain="localhost"
            )

        if tokens.get("refresh_token"):
            response.set_cookie(
                key="refresh_token",
                value=tokens["refresh_token"],
                httponly=True,
                secure=False,  # Set to True in production
                samesite='Lax',
                max_age=tokens.get("refresh_expires_in", 1800),
                path="/",
                domain="localhost"
            )

        response.set_cookie(
            key="csrf_token",
            value=csrf_token,
            httponly=False,
            secure=False,  # Set to True in production
            samesite='Strict',
            max_age=tokens.get("expires_in", 300),
            path="/",
            domain="localhost"
        )

        return schemas.LoginResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            # Default to empty string if missing
            id_token=tokens.get("id_token", ""),
            token_type=tokens.get("token_type", "Bearer"),
            expires_in=tokens.get("expires_in", 300),
            refresh_expires_in=tokens.get("refresh_expires_in", 1800)
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during login"
        )


@router.get("/callback")
async def callback(request: Request):
    """
    Handles the authorization callback, exchanges code for a token,
    and redirects the user to the frontend with the token.
    """

    code = request.query_params.get("code")
    if not code:
        raise HTTPException(
            status_code=400, detail="Authorization code not provided"
        )

    token_url = f"{ISSUER}/protocol/openid-connect/token"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.keycloak_redirect_uri,
        "client_id": settings.keycloak_client_id,
        "client_secret": settings.keycloak_client_secret,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(token_url, data=data)
            response.raise_for_status()
            token_data = response.json()
        except httpx.HTTPError as e:
            logger.error(f"Token exchange failed: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to exchange code for token: {e}",
            )

    if response.status_code != 200:
        logger.error(f"Token exchange failed: {response.json()}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to exchange code for token: {response.json()}",
        )

    token_data = response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(
            status_code=400,
            detail="Access token not found in response",
        )

    logger.info(f"Token exchange successful: {access_token}")
    # frontend_redirect_uri = f"http://localhost:5173/callback?token={access_token}"
    # frontend_redirect_uri = f"{settings.keycloak_redirect_uri}?token={access_token}"
    # logger.info(f"Redirecting to frontend with token: {frontend_redirect_uri}")
    return RedirectResponse(url=f"{request.query_params.get('state', '/')}?token={access_token}")
    # return RedirectResponse(url=frontend_redirect_uri)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


@router.get("/protected")
async def protected_route(token: str = Depends(oauth2_scheme)):
    user_info = await validate_access_token(token)
    return {"message": f"Welcome {user_info['preferred_username']}!"}


@router.post("/refresh-token", response_model=schemas.LoginResponse)
async def refresh_token(refresh_req: schemas.RefreshTokenRequest, response: Response):
    """Refresh access token using refresh token."""
    try:
        tokens = await keycloak_service.refresh_token(refresh_req.refresh_token)

        # Set cookies
        response.set_cookie(
            key="access_token",
            value=tokens["access_token"],
            httponly=True,
            secure=False,  # Set to True in production
            samesite='Lax',
            max_age=tokens["expires_in"],
            path="/",
            domain="localhost"
        )

        response.set_cookie(
            key="refresh_token",
            value=tokens["refresh_token"],
            httponly=True,
            secure=False,  # Set to True in production
            samesite='Lax',
            max_age=tokens["refresh_expires_in"],
            path="/",
            domain="localhost"
        )

        return schemas.LoginResponse(**tokens)
    except HTTPException as e:
        raise e


@router.post("/logout")
async def logout(response: Response):
    """
    Logout user by clearing cookies.
    """
    response.delete_cookie(key="access_token", path="/", domain="localhost")
    response.delete_cookie(key="refresh_token", path="/", domain="localhost")
    response.delete_cookie(key="id_token", path="/", domain="localhost")
    response.delete_cookie(key="csrf_token", path="/", domain="localhost")
    return {"message": f"User{user.username}Logged out successfully"}

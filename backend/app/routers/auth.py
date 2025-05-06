# app/routers/auth.py
from fastapi import APIRouter,  HTTPException, Depends, status, Request, Response, Cookie
from fastapi.responses import RedirectResponse
# from passlib.context import CryptContext
# from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
# from starlette.middleware.sessions import SessionMiddleware
# from keycloak import KeycloakOpenID
# from sqlalchemy.orm import Session
import jwt
from jose import JWTError
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError

from ..utils.utils import hash_password
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db
from ..services.keycloak import KeycloakService
from ..dependencies import get_current_user_from_keycloak_with_role
import requests
import httpx
# import bcrypt
import secrets
import logging
import json
# from ..database import get_db
# from ..models import User

from typing import Annotated


from ..config import settings

# Initialize bcrypt password context
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Create Keycloak client and setup constants
logger = logging.getLogger(__name__)

keycloak_service = KeycloakService()
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.keycloak_server_url}realms/{settings.keycloak_realm}/protocol/openid-connect/token"
)
# Configure JWT settings
ALGORITHMS = ["RS256"]
PUBLIC_KEY = settings.keycloak_public_key
AUDIENCE = settings.keycloak_audience
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


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    """
    Validate the Bearer token and retreive the current user.
    """
    user = keycloak_service.decode_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_user_from_keycloak(token: str = Depends(oauth2_scheme)) -> schemas.User:
    """
    Validate the Bearer token and retrieve the current user from Keycloak.
    """
    try:
        claims = keycloak_service.decode_token(token)
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
        keycloak_user_id = await keycloak_service.create_user(
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
async def login(login_req: schemas.LoginRequest, response: Response, db: Session = Depends(get_db)):
    try:
        tokens = await keycloak_service.authenticate_user(
            login_req.username, login_req.password)

        db_user = db.query(models.User).filter(
            models.User.username == login_req.username).first()
        if not db_user:
            logger.warning(
                f"User {login_req.username} authenticated with keycloak but not found in local database")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in application database"
            )

        role = db.query(models.Role).filter(
            models.Role.id == db_user.role_id).first()
        if not role:
            logger.warning(
                f"Role ID {db_user.role_id} not found for user {login_req.username}")
            role_name = "UNKOWN"
        else:
            role_name = role.name

        # user_info = keycloak_service.decode_token(tokens["access_token"])

        csrf_token = secrets.token_hex(16)

        user_payload = {
            "user_id": db_user.user_id,
            "keycloak_id": db_user.keycloak_id,
            "email": db_user.email,
            "username": db_user.username,
            "first_name": db_user.first_name,
            "last_name": db_user.last_name,
            "role": role_name,
        }

        # user_payload_str = json.dumps(user_payload)

        # Set cookies for the tokens we have
        response.set_cookie(
            key="access_token",
            value=tokens["access_token"],
            httponly=True,
            secure=False,  # Set to True in production
            samesite='Lax',
            max_age=tokens.get("expires_in", 300),
            path="/",
            # domain="localhost"
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
                # domain="localhost"
            )

        response.set_cookie(
            key="csrf_token",
            value=csrf_token,
            httponly=False,
            secure=False,  # Set to True in production
            samesite='Strict',
            max_age=tokens.get("expires_in", 300),
            path="/",
            # domain="localhost"
        )

        logger.info(
            f"User {login_req.username} logged in successfully with role: {role_name}")

        response.headers["Access-Control-Allow-Credentials"] = "true"

        return schemas.LoginResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            id_token=tokens.get("id_token", ""),
            token_type=tokens.get("token_type", "Bearer"),
            expires_in=tokens.get("expires_in", 300),
            refresh_expires_in=tokens.get("refresh_expires_in", 1800),
            csrf_token=csrf_token,
            user_info=user_payload
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during login"
        )


@router.get("/check-auth")
async def check_auth(request: Request, db: Session = Depends(get_db)):
    """
    Check if user is authenticated and return their information
    """
    # Get access token from cookie
    access_token = request.cookies.get("access_token")
    if not access_token:
        return {"authenticated": False, "message": "No access token found"}

    try:
        # Decode token and get user info
        user_claims = await keycloak_service.decode_token(access_token)
        username = user_claims.get("preferred_username")

        # Cross-check with our database
        db_user = db.query(models.User).filter(
            models.User.username == username).first()
        if not db_user:
            return {
                "authenticated": True,
                "keycloak_verified": True,
                "db_verified": False,
                "message": "User authenticated with Keycloak but not found in database"
            }

        # Get role information
        role = db.query(models.Role).filter(
            models.Role.id == db_user.role_id).first()

        return {
            "authenticated": True,
            "keycloak_verified": True,
            "db_verified": True,
            "user_id": db_user.user_id,
            "username": db_user.username,
            "email": db_user.email,
            "role": role.name if role else "UNKNOWN",
            "role_id": db_user.role_id
        }

    except Exception as e:
        logger.error(f"Authentication check failed: {e}")
        return {"authenticated": False, "message": "Invalid or expired token"}


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


@router.post("/reset-password", response_model=dict)
async def reset_password(email: str, new_password: str, db: Session = Depends(get_db)):
    """
    Reset the user's password using Keycloak and update it in the local database.
    """
    try:
        # Fetch the user from the database
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User with the provided email does not exist"
            )

        # Reset the password in Keycloak
        keycloak_service.reset_password(user.keycloak_id, new_password)

        # Update the password in the local database
        user.password_hash = hash_password(new_password)
        db.commit()
        db.refresh(user)

        return {"message": "Password reset successfully"}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Password reset failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resetting the password"
        )


@router.post("/logout")
async def logout(response: Response):
    """
    Logout user by clearing cookies.
    """
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
    response.delete_cookie(key="id_token", path="/")
    response.delete_cookie(key="csrf_token", path="/")
    # return {"message": f"User{User.username}Logged out successfully"}

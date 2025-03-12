# # app/routers/auth.py
# from fastapi import APIRouter, Request, Depends, status, HTTPException
# from fastapi.responses import RedirectResponse
# # from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# # from starlette.middleware.sessions import SessionMiddleware
# from keycloak import KeycloakOpenID
# from jose import JWTError
# from jwt import decode, exceptions as jwt_exceptions, PyJWKClient
# import secrets
# import jwt
# import requests
# import logging
# from pathlib import Path
# # from authlib.integrations.starlette_client import OAuth
# import uuid
# # from ..auth import oauth
# from ..utils.utils import hash_password
# from sqlalchemy.orm import Session
# from .config import settings
# from . import models, schemas
# from .database import get_db
# from .services.keycloak import KeycloakService
# # from app.dependencies import get_public_key


# router = APIRouter(
#     prefix="/auth",
#     tags=["auth"],
#     responses={404: {"description": "Not found"}},
# )

# # Configure Keycloak Client
# # Create Keycloak client and setup constants
# logger = logging.getLogger(__name__)

# def get_public_key():
#     url = f'{settings.keycloak_server_url}/realms/{settings.keycloak_realm}'
#     response = requests.get(url)
#     realm_info = response.json()
#     public_key = realm_info['public_key']
#     return f"-----BEGIN PUBLIC KEY-----\n{public_key}\n-----END PUBLIC KEY-----"


# keycloak_service = KeycloakService()


# @router.post("/signup", response_model=schemas.SignupResponse)
# async def signup(signup_req: schemas.SignupRequest, db: Session = Depends(get_db)):
#     # Check if user already exists 
#     existing_user = db.query(models.User).filter(
#         (models.User.email == signup_req.email) | 
#         (models.User.username == signup_req.username)
#     ).first()
#     if existing_user:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Email or Username already registered"
#         )
#     try:
#         # Create user in Keycloak 
#         keycloak_user_id = keycloak_service.create_user(
#             email=signup_req.email,
#             username=signup_req.username,
#             password_hash=signup_req.password_hash,
#             first_name=signup_req.first_name,
#             last_name=signup_req.last_name,
#             role=signup_req.role
#         )
#     except Exception as e:
#         logging.error(f"Keycloak user creation failed: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Failed to create user in authentication service"
#         )
    

#     # Hash the password before saving local 
#     hashed_pw = hash_password(signup_req.password_hash)


#     # Create user in local DB
#     user = models.User(
#         # keycloak_id=keycloak_user_id,
#         email= signup_req.email,
#         username= signup_req.username,
#         password_hash=hashed_pw,
#         first_name=signup_req.first_name,
#         last_name=signup_req.last_name,
#         role=signup_req.role
#     )

#     db.add(user)
#     db.commit()
#     db.refresh(user)


#     return schemas.SignupResponse(
#         user_id=user.user_id,
#         # keycloak_id= user.keycloak_id,
#         email= user.email,
#         username= user.username,
#         first_name= user.first_name,
#         last_name=user.last_name,
#         role=user.role,
#         message=f"USer {user.username} ws created succesfully!"
#     )


# @router.get("/login", response_model=schemas.LoginResponse)
# async def login(login_req: schemas.LoginRequest, db: Session= Depends(get_db)):
#     try:

#         # Authenticate with keycloak 
#         token = keycloak_service.authenticate_user(
#             username=login_req.username,
#             password_hash=login_req.password_hash
#         )
#     except Exception as e:
#         logging.error(f"Authentification failed: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid username or password",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
    
#     return schemas.LoginResponse(
#         access_token=token.get("access_token"),
#         refresh_token=token.get("refresh_token"),
#         token_type=token.get("token_type"),
#         expires_in=token.get("epxires_in"),
#         refresh_expires_in=token.get("refresh_expires_in"),
#         refresh_token_expires_in=token.get("refresh_expires_in"),
#         session_state=token.get("session_state"),
#         scope=token.get("scope")
#     )
    
#         # STEP: Generating the auth url
#     auth_url = keycloak_openid.auth_url(redirect_uri=settings.keycloak_redirect_uri,
#                                         state=state,
#                                         scope="openid")

#     return RedirectResponse(url=auth_url)


# @router.get("/callback")
# async def callback(request: Request):
#     """
#     Handles Keycloak callback to exchange auth code for tokens and store them in the session.
#     """

#     keycloak_openid = get_keycloak_client()

#     state = request.query_params.get("state")
#     code = request.query_params.get("code")
#     # token = await oauth.keycloak.authorize_access_token(request)

#     if not code:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST, detail='AUTH code is missing')

#     saved_state = request.session.get('state')
#     if state != saved_state:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST, detail='AUTH code is missing')

# # STEP: Exchange the code for any access token
#     token = keycloak_openid.token(
#         grant_type='authorization_code',
#         code=code,
#         redirect_uri=settings.keycloak_redirect_uri
#     )
#     if 'access_token' not in token:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token response')

# # Retreive user info using the access token
#     # user_info = await oauth.keycloak.parse_id_token(request,token)
#     user_info = keycloak_openid.userinfo(token['access_token'])

#     if not user_info:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED, detail='Failed to fetch User Info')

#     response = RedirectResponse(url=request.session.get('next', '/'))
#     response.set_cookie(
#         key='access_token',
#         value=token['access_token'],
#         httponly=True,
#         secure=False,
#         samesite='lax'
#     )
#     if 'refresh_token' in token:
#         response.set_cookie(
#             key="refresh_token",
#             value=token['refresh_token'],
#             httponly=True,
#             secure=False,
#             samesite='lax')

#         request.session.pop('state', None)
#         request.session.pop('next', None)

#         return response


# @router.get("/logout")
# async def logout(request: Request):
#     keycloak_openid = get_keycloak_client()

#     # Get tokens from cookies
#     refresh_token = request.cookies.get('refresh_token')

#     if not refresh_token:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED, detail='No refresh token found')

#     # Logout via Keycloak
#     keycloak_openid.logout(refresh_token)

#     # Clear cookies
#     response = RedirectResponse(url="/")
#     response.delete_cookie("access_token")
#     response.delete_cookie("refresh_token")

#     return response


# @router.get("/token")
# async def get_token(token: str):
#     try:
#         payload = jwt.decode(
#             token, PUBLIC_KEY, algorithms=ALGORITHMS, audience=AUDIENCE, issuer=ISSUER)
#         return payload
#     except JWTError as e:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid token",
#             headers={"WWW-Authenticate": "Bearer"},
#         ) from e

# app/routers/users.py


from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List
from ..database import SessionLocal
import json
import logging
from ..dependencies import require_roles, get_current_user_from_cookies, valid_access_token, get_current_user
# from ..models import U
from .. import schemas, models
from ..models import User as DBUser, Role, Profile
from ..services.keycloak import KeycloakService
from ..utils.utils import hash_password
from ..utils.cache import get_cached_users, invalidate_users_cache, cache_users_response


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Not found"}},
)

# Dependency to get DB session


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


keycloak_service = KeycloakService()

# def hash_password(password: str) -> str:
#     return pwd_context.hash(password)


# def verify_password(plain_password: str, hash_password: str) -> bool:
#     return pwd_context.verify(plain_password, hashed_password)


# backend/app/routers/users.py

@router.post('/', response_model=schemas.SignupResponse)
async def create_user(user: schemas.SignupRequest, db: Session = Depends(get_db)) -> schemas.SignupResponse:
    existing_user = db.query(DBUser).filter(
        (DBUser.email == user.email) |
        (DBUser.username == user.username)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered"
        )

    hashed_password = hash_password(user.password)
    role = db.query(Role).filter(Role.name == user.role.upper()).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Role not found")

    try:
        keycloak_id = keycloak_service.create_user(
            email=user.email,
            username=user.username,
            password=user.password,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role.upper()
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Failed to create user in Keycloak") from e

    new_user = DBUser(
        keycloak_id=keycloak_id,
        username=user.username,
        email=user.email,
        password_hash=hashed_password,
        first_name=user.first_name,
        last_name=user.last_name,
        role_id=role.id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    await invalidate_users_cache()

    return schemas.SignupResponse(
        user_id=new_user.user_id,
        keycloak_id=new_user.keycloak_id,
        email=new_user.email,
        username=new_user.username,
        first_name=new_user.first_name,
        last_name=new_user.last_name,
        role=role.name,
        message="User created successfully!"
    )


@router.get('/', response_model=List[schemas.User])
async def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)) -> List[schemas.User]:
    # logger.info(
        # f"User {current_user.username} is fetching users list with pagination")

    # Validate pagination parameters
    if limit > 100:
        limit = 100
    if skip < 0:
        skip = 0

    cached_users = await get_cached_users(db)
    if cached_users:
        logger.info("Returning cached users")
        return cached_users[skip:skip + limit]

    # Use efficient join query with pagination
    query = (
        db.query(models.User, models.Role)
        .outerjoin(models.Role, models.User.role_id == models.Role.id)
        .offset(skip)
        .limit(limit)
    )

    # Execute query and get results
    results = query.all()

    if not results:
        logger.warning("No users found")
        raise HTTPException(status_code=404, detail="No users found")

    # Serialize results efficiently
    serialized_users = [
        schemas.User(
            user_id=user.user_id,
            keycloak_id=user.keycloak_id,
            email=user.email,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            role=role.name if role else None
        )
        for user, role in results
    ]

    # Cache the results
    await cache_users_response(serialized_users)

    return serialized_users


@router.get("/admin")
@router.get("/{user_id}", response_model=schemas.User)
async def read_user(user_id: int, db: Session = Depends(get_db)) -> schemas.User:
    user = db.query(DBUser).filter(DBUser.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return schemas.User(
        user_id=user.user_id,
        keycloak_id=user.keycloak_id,
        email=user.email,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        role=role.name if role else None
    )


@router.put("/{user_id}", response_model=schemas.User)
async def update_user(user_id: int, user_update: schemas.UserUpdate, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    # if not current_user:
    user = db.query(DBUser).filter(DBUser.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
 
    if current_user.user_id != user_id and current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Not authorized")

    # if user_update.password:
    #     user.password_hash = hash_password(user_update.password)
    # if user_update.role:
    #     role = db.query(Role).filter(
    #         Role.name == user_update.role.upper()).first()
    #     if not role:
    #         raise HTTPException(status_code=400, detail="Role not found")
    #     user.role_id = role.id

    for key, value in user_update.dict(exclude_unset=True).items():
        if key not in ['password', 'role']:
            setattr(user, key, value)

    db.commit()
    db.refresh(user)
    await invalidate_users_cache()
    # role = db.query(Role).filter(Role.id == user.role_id).first()
    return schemas.User(
        user_id=user.user_id,
        keycloak_id=user.keycloak_id,
        email=user.email,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        role=current_user.role
    )           


    await cache_users_response([serialized_user_update])

    return serialized_user_update


@router.delete('/{user_id}', response_model=dict)
async def delete_user(user_id: int, db: Session = Depends(get_db)) -> dict:
    user = db.query(DBUser).filter(DBUser.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        keycloak_service.delete_user(user.keycloak_id)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Failed to delete user from Keycloak") from e

    db.delete(user)
    db.commit()
    await invalidate_users_cache()
    return {"message": "User deleted successfully"}

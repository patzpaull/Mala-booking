# app/routers/services.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import SessionLocal, engine
from ..models import Profile
from .. import models, schemas
from ..utils.cache import get_cached_profiles, invalidate_cache

router = APIRouter(
    prefix="/profiles",
    tags=["profiles"],
    responses={404: {"description": "Not found"}},
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/")
async def create_profile(profile_create: schemas.ProfileCreate, db: Session = Depends(get_db)
                         ) -> schemas.Profile:
    """
    Create a new User Profile
    """

    db_user = db.query(models.User).filter(
        models.User.user_id == profile_create.user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User Not Found")

    db_profile = models.Profile(
        user_id=profile_create.user_id,
        bio=profile_create.bio,
        avatar_url=profile_create.avatar_url,
        username=db_user.username
    )
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    # await invalidate_cache("profiles:*")

    return {
        "profile_id": db_profile.profile_id,
        "user_id": db_profile.user_id,
        "username": db_user.username,
        "bio": db_profile.bio,
        "avatar_url": db_profile.avatar_url
    }


@router.get("/{user_id}")
async def read_profile(user_id: int, db: Session = Depends(get_db)
                       ) -> dict:
    """
    Get a User's Combined Profile
    """

    # Fetch user
    db_user = db.query(models.User).filter(
        models.User.user_id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not Found")

    # Fetch profile
    db_profile = db.query(models.Profile).filter(
        models.Profile.user_id == user_id).first()
    if not db_profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # combine user and profile data
    return {
        "user_id": db_user.user_id,
        "username": db_user.username,
        "email": db_user.email,
        "first_name": db_user.first_name,
        "last_name": db_user.last_name,
        "profile": {
            "bio": db_profile.bio,
            "avatar_url": db_profile.avatar_url
        }
    }


@router.put('/{user_id}')
async def update_profile(user_id: int, profile_update: schemas.ProfileUpdate, db: Session = Depends(get_db)
                         ) -> schemas.Profile:
    """
    Update a User's profile
    """
    # db_profile = db.get(models.Profile, user_id)
    db_profile = db.query(models.Profile).filter(
        models.Profile.user_id == user_id).first()
    if db_profile is None:
        raise HTTPException(
            status_code=404, detail='Profile was not found')

    for key, val in profile_update.model_dump(exclude_none=True).items():
        setattr(db_profile, key, val)

    db.commit()
    db.refresh(db_profile)
    # await invalidate_cache("profile:*")

    # user = db.query(models.User).filter(models.User.user_id == user_id).first()

    return {
        "profile_id": db_profile.profile_id,
        "username": db_profile.username,
        "bio": db_profile.bio,
        "avatar_url": db_profile.avatar_url
    }


@router.delete('/{user_id}')
async def delete_profile(user_id: int, db: Session = Depends(get_db)) -> dict:
    """
    Deletes an User's Profile
    """
    # db_profile = db.query(models.Profile).filter(models.Profile.user_id == user_id).first()
    db_profile = db.query(models.Profile).filter(
        models.Profile.user_id == models.User.user_id).first()
    if not db_profile:
        raise HTTPException(
            status_code=404, detail="User Profile was not found")

    db_user = db.query(models.User).filter(
        models.User.user_id == user_id).first()

    db.delete(db_profile)
    db.commit()
    # await invalidate_cache("profiles:*")
    return {'message': f'The profile for user {db_user.username} was succesfully deleted'}

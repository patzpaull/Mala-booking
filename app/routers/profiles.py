# app/routers/services.py

from typing import List
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..utils.utils import hash_password, get_role_id_by_name
from ..dependencies import get_current_user, require_roles
import logging
import os
import io
import json
from .. import models, schemas
from ..config import settings
from ..services.keycloak import KeycloakService
from ..utils.cache import get_cached_profiles, invalidate_profiles_cache, cache_profiles_response, cache
from ..services.storage import storage_service
from ..utils.image_processor import image_processor
from datetime import datetime as dt
# from google.oauth2 import service_account
# from googleapiclient.discovery import build
# from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

router = APIRouter(
    prefix="/profiles",
    tags=["profiles"],
    responses={404: {"description": "Not found"}},
)


keycloak_service = KeycloakService()

logger = logging.getLogger(__name__)

# SCOPES = settings.google_scopes
# SERVICE_ACCOUNT_FILE = settings.google_service_account

# credentials = service_account.Credentials.from_service_account_file(
    # SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# drive_service = build('drive', 'v3', credentials=credentials)




def combine_user_profile(db_user: models.User, db_profile: models.Profile) -> schemas.Profile:
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


def check_profile_access(keycloak_id: str, current_user: schemas.User) -> bool:
    """
    Check if current user can access the profile.
    Returns True if:
    1. User is an admin/superuser
    2. User is accessing their own profile (keycloak_id matches)
    """
    # Admin and superuser can access any profile
    if current_user.role in ["admin", "superuser"]:
        return True

    # User can access their own profile
    if current_user.keycloak_id == keycloak_id:
        return True

    return False


@router.post("/signup", response_model=schemas.Profile)
async def create_customer_profile(profile_create: schemas.ProfileCreate, db: Session = Depends(get_db)) -> schemas.Profile:
    """
    Create a new user profile (role-specific) and log the user in
    """

    # Sanitize input
    profile_create.firstName = profile_create.firstName.strip()
    profile_create.lastName = profile_create.lastName.strip()
    # profile_create.email = profile_create.email.strip()
    # profile_create.phoneNumber = profile_create.phoneNumber.strip()
    # profile_create.address = profile_create.address.strip()
    # profile_create.bio = profile_create.bio.strip()
    # profile_create.avatar_url = profile_create.avatar_url.strip()
    # if getattr(profile_create, "username", None):
        # profile_create.username = profile_create.username.strip()
    # else:
    profile_username = (profile_create.firstName + profile_create.lastName).lower().replace(" ", "")

    # Register the user in Keycloak
    try:
        keycloak_id = await keycloak_service.create_user_async(
            username=profile_username,
            email=profile_create.email,
            first_name=profile_create.firstName,
            last_name=profile_create.lastName,
            password=profile_create.password,
            role=(profile_create.userType or "CUSTOMER").upper()
        )
        logger.info(f"Keycloak user created: {keycloak_id}")
    except HTTPException as e:
        # raise e
        logging.error(f"Keycloak user creation failed: {e.detail}")
        raise HTTPException(status_code=e.status_code, detail=f"Keycloak creation failed: {e.detail}")
    except Exception as e:
        logging.error(f"Unexpected error during Keycloak user creation: {e}")
        raise HTTPException(
            status_code=500, detail="Unexpected error during user creation")
    # Get role_id from role name
    role_id = get_role_id_by_name(db, profile_create.userType)
    if not role_id:
        logging.error(f"Invalid role: {profile_create.userType}")
        await keycloak_service.delete_user(keycloak_id)
        raise HTTPException(
            status_code=400, detail=f"Invalid role: {profile_create.userType}")

    # Persist local user (Avoid nested transaction)
    try:
            user = models.User(
                keycloak_id=keycloak_id,
                email=profile_create.email,
                username=profile_username,
                first_name=profile_create.firstName,
                last_name=profile_create.lastName,
                password_hash=hash_password(profile_create.password),
                role_id=role_id
            )
            db.add(user)
            db.flush()
            db.refresh(user)
    except Exception as e:
        logging.error(f"Database operation failed: {e}")
        db.rollback()
        await keycloak_service.delete_user(keycloak_id)
        raise HTTPException(
            status_code=500, detail="An error occured while saving the user to the database. ")
    # Create the profile in the database
    try:
        # Create a new profile
        db_profile = models.Profile(
            user_id=user.user_id,
            keycloak_id=keycloak_id,
            firstName=profile_create.firstName,
            lastName=profile_create.lastName,
            email=profile_create.email,
            phone_number=profile_create.phone_number,
            address=profile_create.address,
            bio=profile_create.bio,
            avatar_url=profile_create.avatar_url,
            userType=profile_create.userType,
            status="ACTIVE",
            additionalData=profile_create.additionalData,
            username=profile_username
        )
        db.add(db_profile)
        db.commit()
        db.refresh(db_profile)
    except Exception as e:
        logging.error(f"Database operation failed: {e}")
        await keycloak_service.delete_user(keycloak_id)
        db.delete(user)
        db.commit()
        raise HTTPException(
            status_code=500, detail="An error occured while saving the profile to the database. ")

    # Log the user in and generate tokens
    try:
        tokens = await keycloak_service.authenticate_user(
            username=profile_create.email,
            password=profile_create.password
        )
    except HTTPException as e:
        logging.error(f"Keycloak login failed: {e.detail}")
        raise HTTPException(status_code=e.status_code,
                            detail=f"An error occured while logging the user in")

    # Return the profile and tokens
    return schemas.Profile(
        user_id=user.user_id,
        keycloak_id=keycloak_id,
        username=profile_username,
        firstName=profile_create.firstName,
        lastName=profile_create.lastName,
        email=profile_create.email,
        phone_number=profile_create.phone_number,
        address=profile_create.address,
        bio=profile_create.bio,
        avatar_url=profile_create.avatar_url,
        userType=profile_create.userType,
        status="ACTIVE",
        additionalData=profile_create.additionalData,
        tokens=tokens)


@router.get("/customers/{keycloak_id}", response_model=schemas.Profile)
async def read_customer_profile(keycloak_id: str,
                                db: Session = Depends(get_db),
                                current_user: schemas.User = Depends(get_current_user)
                                ) -> schemas.Profile:
    """
    Get a Customer's Profile by keycloak_id
    Accessible by: Profile owner OR admin
    """

    # Check access rights
    if not check_profile_access(keycloak_id, current_user):
        raise HTTPException(
            status_code=403, detail="You don't have permission to access this profile")

    cached_profile = await get_cached_profiles(keycloak_id, db)
    if cached_profile:
        logging.info(f"Returning cached profile for keycloak_id: {keycloak_id}")
        return cached_profile

    # Fetch profile
    db_profile = db.query(models.Profile).filter(
        models.Profile.keycloak_id == keycloak_id, models.Profile.userType == "CUSTOMER").first()

    if not db_profile:
        raise HTTPException(
            status_code=404, detail="Profile Not Found. Please create or update your profile")

    profile_dict = db_profile.to_dict()

    await cache_profiles_response([db_profile])

    return schemas.Profile.model_validate(profile_dict)


@router.get("/", response_model=List[schemas.Profile])
async def read_profiles(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: schemas.User = Depends(require_roles(["admin", "superuser"]))) -> List[schemas.Profile]:
    """
    Retrieve all profiles (paginated)
    Admin/Superuser only - for listing all profiles
    """

    logger.info("Fetching profiles with pagination")

    if limit > 100:
        limit = 100
    if skip < 0:
        skip = 0

    cached_profiles = await cache.get('profiles_list')
    if cached_profiles:
        logger.info("Returning cached profiles")
        cached_data = json.loads(cached_profiles) if isinstance(cached_profiles, str) else cached_profiles
        return cached_data[skip:skip + limit]

    query = (
        db.query(models.Profile)
        .offset(skip)
        .limit(limit)
    )

    profiles = query.all()

    if not profiles:
        logger.warning("No profiles found")
        raise HTTPException(status_code=404, detail="No profiles found")

    serialized_profiles = [
        schemas.Profile.model_validate(profile.to_dict())
        for profile in profiles
    ]

    await cache_profiles_response(profiles)

    return serialized_profiles


@router.put('/vendors/{keycloak_id}', response_model=schemas.Profile)
async def update_profile(keycloak_id: str, profile_update: schemas.ProfileUpdate, db: Session = Depends(get_db)
                         ) -> schemas.Profile:
    """
    Update a Vendor's profile
    """
    # db_profile = db.get(models.Profile, user_id)
    db_profile = db.query(models.Profile).filter(
        models.Profile.keycloak_id == keycloak_id, models.Profile.userType == "VENDOR").first()

    if not db_profile:
        raise HTTPException(
            status_code=404, detail="Vendor Profile was not found")

    for key, val in profile_update.model_dump(exclude_none=True).items():
        setattr(db_profile, key, val)

    db.commit()
    db.refresh(db_profile)
    await invalidate_profiles_cache()
    return db_profile


@router.patch("/customers/{keycloak_id}", response_model=schemas.Profile)
async def patch_customer_profile(keycloak_id: str, profile_patch: schemas.ProfileUpdate, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)) -> schemas.Profile:
    """
    Partially update a Customer's profile
    Accessible by: Profile owner OR admin
    """
    # Check access rights
    if not check_profile_access(keycloak_id, current_user):
        raise HTTPException(
            status_code=403, detail="You don't have permission to update this profile")

    db_profile = db.query(models.Profile).filter(
        models.Profile.keycloak_id == keycloak_id, models.Profile.userType == "CUSTOMER").first()

    if not db_profile:
        raise HTTPException(
            status_code=404, detail="Customer Profile was not found")

    for key, val in profile_patch.model_dump(exclude_none=True).items():
        setattr(db_profile, key, val)

    db.commit()
    db.refresh(db_profile)
    await invalidate_profiles_cache()

    profile_dict = db_profile.to_dict()
    return schemas.Profile.model_validate(profile_dict)


@router.post("/{user_type}/{keycloak_id}/avatar", response_model=schemas.AvatarUploadResponse)
async def upload_avatar(
    user_type: str,
    keycloak_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
) -> schemas.AvatarUploadResponse:
    """
    Upload or update user avatar
    Accessible by: User themselves OR admin/superuser

    Supports: CUSTOMER, VENDOR, ADMIN, FREELANCE
    """
    # Validate user type
    user_type = user_type.upper()
    valid_types = ['CUSTOMER', 'VENDOR', 'ADMIN', 'FREELANCE']
    if user_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user type. Must be one of: {', '.join(valid_types)}"
        )

    # Check access rights
    if not check_profile_access(keycloak_id, current_user):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to upload avatar for this profile"
        )

    # Verify profile exists
    db_profile = db.query(models.Profile).filter(
        models.Profile.keycloak_id == keycloak_id,
        models.Profile.userType == user_type
    ).first()

    if not db_profile:
        raise HTTPException(
            status_code=404,
            detail=f"{user_type.capitalize()} profile not found"
        )

    # Validate and process image
    await image_processor.validate_avatar(file)
    processed_file, ext = await image_processor.process_avatar(file)

    # Create a temporary UploadFile from processed image
    from fastapi import UploadFile as FastAPIUploadFile
    temp_file = FastAPIUploadFile(
        filename=f"avatar.{ext}",
        file=processed_file
    )
    temp_file.content_type = f"image/{ext}"

    # Upload to Spaces
    avatar_url = await storage_service.upload_avatar(temp_file, keycloak_id, user_type)

    # Update database
    db_profile.avatar_url = avatar_url
    db.commit()
    db.refresh(db_profile)

    await invalidate_profiles_cache()

    return schemas.AvatarUploadResponse(
        message="Avatar uploaded successfully",
        file_url=avatar_url,
        uploaded_at=dt.now(),
        user_type=user_type,
        keycloak_id=keycloak_id
    )


@router.delete("/{user_type}/{keycloak_id}/avatar", response_model=dict)
async def delete_avatar(
    user_type: str,
    keycloak_id: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
) -> dict:
    """
    Delete user avatar
    Accessible by: User themselves OR admin/superuser
    """
    # Validate user type
    user_type = user_type.upper()
    valid_types = ['CUSTOMER', 'VENDOR', 'ADMIN', 'FREELANCE']
    if user_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user type. Must be one of: {', '.join(valid_types)}"
        )

    # Check access rights
    if not check_profile_access(keycloak_id, current_user):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to delete avatar for this profile"
        )

    # Verify profile exists
    db_profile = db.query(models.Profile).filter(
        models.Profile.keycloak_id == keycloak_id,
        models.Profile.userType == user_type
    ).first()

    if not db_profile:
        raise HTTPException(
            status_code=404,
            detail=f"{user_type.capitalize()} profile not found"
        )

    if not db_profile.avatar_url:
        raise HTTPException(
            status_code=404,
            detail="No avatar found for this profile"
        )

    # Delete from Spaces
    deleted = await storage_service.delete_avatar(
        keycloak_id,
        user_type,
        db_profile.avatar_url
    )

    if deleted:
        # Update database
        db_profile.avatar_url = None
        db.commit()
        await invalidate_profiles_cache()

        return {"message": "Avatar deleted successfully"}
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to delete avatar from storage"
        )


#
#
# def create_folder(folder_name, parent_folder_id=None):
    # """
    # Create a folder in Google Drive and return its ID
    # """
    # folder_metadata = {
        # 'name': folder_name,
        # 'mimeType': 'application/vnd.google-apps.folder',
        # 'parents': [parent_folder_id] if parent_folder_id else []
    # }
# 
    # created_folder = drive_service.files().create(
        # body=folder_metadata,
        # fields='id'
    # ).execute()
# 
    # print(f'Created folder ID: {created_folder.get("id")}')
    # return created_folder.get('id')
# 
# 
# def upload_file_obj(file_obj, file_name, mimetype, parent_folder_id=None):
    # """
    # Upload a file object to Google Drive and return its ID
    # """
    # try:
        # media = MediaIoBaseUpload(file_obj, mimetype=mimetype, resumable=True)
        # file_metadata = {
            # 'name': file_name,
            # 'parents': [parent_folder_id] if parent_folder_id else []
        # }
        # upload_file = drive_service.files().create(
            # body=file_metadata, media_body=media, fields='id').execute()
        # print(f'file uploaded succesfuly. File ID: {upload_file.get("id")}')
        # return upload_file.get('id')
    # except Exception as e:
        # print(f"Error uploading file to Google Drive: {e}")
        # logger.error(f"Error uploading file to Google Drive: {e}")
        # raise HTTPException(
            # status_code=500, detail="Error uploading file to Google Drive")
# 
# 
# @router.post("/{keycloak_id}/avatar", response_model=dict)
# async def manage_avatar(keycloak_id: str, action: str = Query(..., description="Action to perform: upload, update, or delete"), file: UploadFile = File(None), user_type: str = Query("CUSTOMER", description="User type (e.g., CUSTOMER,VENDOR,ADMIN)"), db: Session = Depends(get_db)
                        # ):
    # """
    # Manage Avatars for Users.
    # Supports Upload, Update, and Delete actions
    # """
    # db_profile = db.get(models.Profile, user_id)
    # db_profile = db.query(models.Profile).filter(
        # models.Profile.keycloak_id == keycloak_id, models.Profile.userType == user_type.upper()).first()
# 
    # if not db_profile:
        # raise HTTPException(
            # status_code=404, detail=f"{user_type.capitalize()} Profile was not found")
# 
    # try:
        # if action == "delete":
            # if db_profile.avatar_url:
                # file_id = db_profile.avatar_url.split('id=')[-1]
                # drive_service.files().delete(fileId=file_id).execute()
                # db_profile.avatar_url = None
                # db.commit()
                # db.refresh(db_profile)
                # await invalidate_profiles_cache()
                # return {"message": f"{user_type.capitalize()}. avatar deleted succesfully"}
            # return {"message": f"No avatar to delete for {user_type.capitalize()}"}
# 
        # elif action in ["upload", "update"]:
            # if action == "update" and db_profile.avatar_url:
                # file_id = db_profile.avatar_url.split('id=')[-1]
                # drive_service.files().delete(fileId=file_id).execute()
# 
            # if not file:
                # raise HTTPException(
                    # status_code=400, detail="No file provided for upload")
# 
            # file_content = await file.read()
            # file_stream = io.BytesIO(file_content)
# 
            # file_id = upload_file_obj(
                # file_obj=file_stream, file_name=file.filename, mimetype=file.content_type, parent_folder_id=settings.google_drive_folder_id
            # )
# 
            # drive_service.permissions().create(
                # fileId=file_id, body={'type': 'anyone', 'role': 'reader'}).execute(
            # )
# 
            # avatar_url = f"http://drive.google.com/uc?id={file_id}"
    #         db_profile.avatar_url = avatar_url
    #         db.commit()
    #         db.refresh(db_profile)
    #         await invalidate_profiles_cache()

    #         return {"message": f"{user_type.capitalize()}avatar {action}d Succesfully.", "avatar_url": avatar_url}
    #         # return {"message": "Avatar uploaded successfully", "avatar_url": db_profile.avatar_url}
    #     else:
    #         raise HTTPException(
    #             status_code=400, detail="Invalid action. Use 'upload', 'update', or 'delete'.")
    # except Exception as e:
    #     logger.error(
    #         f"failed to manage avatar for {user_type.capitalize()}: {e}")
    #     raise HTTPException(
    #         status_code=500, detail=f"An error occured while managing the avatar: {e}")
    # # return {"message": "Avatar uploaded successfully", "avatar_url": db_profile.avatar_url}


@router.delete('/customers/{keycloak_id}', response_model=dict)
async def delete_profile(keycloak_id: str, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)) -> dict:
    """
    Deletes a Customer's Profile
    Accessible by: Customer themselves OR admin/superuser
    """
    # Check access rights
    if not check_profile_access(keycloak_id, current_user):
        raise HTTPException(
            status_code=403, detail="You don't have permission to delete this profile")

    db_profile = db.query(models.Profile).filter(
        models.Profile.keycloak_id == keycloak_id, models.Profile.userType == "CUSTOMER").first()

    if not db_profile:
        raise HTTPException(
            status_code=404, detail="User Profile was not found")

    db.delete(db_profile)
    db.commit()

    await invalidate_profiles_cache()
    return {'message': f'The profile for user {keycloak_id} was succesfully deleted'}


@router.put("/admins/{keycloak_id}", response_model=schemas.Profile)
async def update_admin_profile(keycloak_id: str, profile_update: schemas.ProfileUpdate, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)) -> schemas.Profile:
    """
    Update an admin's profile
    Accessible by: Admin themselves OR superuser
    """
    # Check access rights
    if not check_profile_access(keycloak_id, current_user):
        raise HTTPException(
            status_code=403, detail="You don't have permission to update this profile")

    db_profile = db.query(models.Profile).filter(
        models.Profile.keycloak_id == keycloak_id, models.Profile.userType == "ADMIN"
    ).first()

    if not db_profile:
        raise HTTPException(
            status_code=404, detail="Admin profile not found.")

    for key, value in profile_update.model_dump(exclude_none=True).items():
        setattr(db_profile, key, value)

    db.commit()
    db.refresh(db_profile)
    await invalidate_profiles_cache()

    profile_dict = db_profile.to_dict()
    return schemas.Profile.model_validate(profile_dict)


@router.delete("/admins/{keycloak_id}", response_model=dict)
async def delete_admin_profile(keycloak_id: str, db: Session = Depends(get_db), current_user: schemas.User = Depends(require_roles(["superuser"]))) -> dict:
    """
    Delete an admin's profile
    Accessible by: Superuser only
    """
    db_profile = db.query(models.Profile).filter(
        models.Profile.keycloak_id == keycloak_id, models.Profile.userType == "ADMIN"
    ).first()

    if not db_profile:
        raise HTTPException(
            status_code=404, detail="Admin profile not found.")

    db.delete(db_profile)
    db.commit()
    await invalidate_profiles_cache()

    return {"message": f"Admin profile for {keycloak_id} has been deleted."}


@router.get("/admins/analytics", response_model=dict)
async def get_admin_analytics(db: Session = Depends(get_db)) -> dict:
    """
    Retrieve admin analytics data
    """
    total_users = db.query(models.User).count()
    total_profiles = db.query(models.Profile).count()
    total_services = db.query(models.Service).count()
    total_appointments = db.query(models.Appointment).count()
    total_messages = db.query(models.Message).count()
    total_salons = db.query(models.Salon).count()

    total_customers = db.query(models.Profile).filter(
        models.Profile.userType == "CUSTOMER").count()
    total_admins = db.query(models.Profile).filter(
        models.Profile.userType == "ADMIN").count()
    total_freelancers = db.query(models.Profile).filter(
        models.Profile.userType == "FREELANCE").count()
    total_vendors = db.query(models.Profile).filter(
        models.Profile.userType == "VENDOR").count()

    # Salon-specific analytics
    total_active_salons = db.query(models.Salon).filter(
        models.Salon.status == "ACTIVE").count()
    total_inactive_salons = db.query(models.Salon).filter(
        models.Salon.status == "INACTIVE").count()

    salons_by_location = [{"city": city, "total": total}
                          for city, total in db.query(models.Salon.city, func.count(models.Salon.salon_id).label('total'))
                          .group_by(models.Salon.city)
                          .all()]

    # Service analytics
    popular_services = [{"service_name": name, "appointments_booked": appointments_booked}
                        for name, appointments_booked in db.query(models.Service.name, func.count(models.Appointment.appointment_id).label('appointments_booked'))
                        .join(models.Appointment, models.Service.service_id == models.Appointment.service_id)
                        .group_by(models.Service.name)
                        .order_by(func.count(models.Appointment.appointment_id).desc())
                        .limit(5)
                        .all()]

    # Appointment analytics
    appointments_by_status = [{"status": status, "total": total}
                             for status, total in db.query(models.Appointment.status, func.count(models.Appointment.appointment_id).label('total'))
                             .group_by(models.Appointment.status)
                             .all()]

    # Message analytics
    messages_per_appointment = [{"appointment_id": appointment_id, "total_messages": total_messages}
                                for appointment_id, total_messages in db.query(models.Message.appointment_id, func.count(models.Message.id).label('total_messages'))
                                .group_by(models.Message.appointment_id)
                                .all()]

    return {
        "total_users": total_users,
        "total_profiles": total_profiles,
        "total_services": total_services,
        "total_appointments": total_appointments,
        "total_messages": total_messages,
        "total_salons": total_salons,
        "total_vendors": total_vendors,
        "total_customers": total_customers,
        "total_admins": total_admins,
        "total_freelancers": total_freelancers,
        "total_active_salons": total_active_salons,
        "total_inactive_salons": total_inactive_salons,
        "salons_by_location": salons_by_location,
        "popular_services": popular_services,
        "appointments_by_status": appointments_by_status,
        "messages_per_appointment": messages_per_appointment,
    }


@router.get("/vendors/{keycloak_id}", response_model=schemas.Profile)
async def get_vendor_profile(keycloak_id: str, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)) -> schemas.Profile:
    """
    Retrieve a vendor's profile by keycloak_id
    Accessible by: Vendor themselves OR admin/superuser
    """
    # Check access rights
    if not check_profile_access(keycloak_id, current_user):
        raise HTTPException(
            status_code=403, detail="You don't have permission to access this profile")

    cached_profile = await get_cached_profiles(keycloak_id, db)
    if cached_profile:
        logging.info(f"Returning cached profile for keycloak_id: {keycloak_id}")
        return cached_profile

    db_profile = db.query(models.Profile).filter(
        models.Profile.keycloak_id == keycloak_id, models.Profile.userType == "VENDOR"
    ).first()

    if not db_profile:
        raise HTTPException(
            status_code=404, detail="Vendor profile not found.")

    profile_dict = db_profile.to_dict()
    await cache_profiles_response([db_profile])

    return schemas.Profile.model_validate(profile_dict)


@router.put("/vendors/{keycloak_id}", response_model=schemas.Profile)
async def update_vendor_profile(keycloak_id: str, profile_update: schemas.ProfileUpdate, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)) -> schemas.Profile:
    """
    Update a vendor's profile
    Accessible by: Vendor themselves OR admin/superuser
    """
    # Check access rights
    if not check_profile_access(keycloak_id, current_user):
        raise HTTPException(
            status_code=403, detail="You don't have permission to update this profile")

    db_profile = db.query(models.Profile).filter(
        models.Profile.keycloak_id == keycloak_id, models.Profile.userType == "VENDOR"
    ).first()

    if not db_profile:
        raise HTTPException(
            status_code=404, detail="Vendor profile not found.")

    for key, value in profile_update.model_dump(exclude_none=True).items():
        setattr(db_profile, key, value)

    db.commit()
    db.refresh(db_profile)
    await invalidate_profiles_cache()

    profile_dict = db_profile.to_dict()
    return schemas.Profile.model_validate(profile_dict)


@router.delete("/vendors/{keycloak_id}", response_model=dict)
async def delete_vendor_profile(keycloak_id: str, db: Session = Depends(get_db), current_user: schemas.User = Depends(require_roles(["admin", "superuser"]))) -> dict:
    """
    Delete a vendor's profile
    Accessible by: Admin or Superuser only
    """
    db_profile = db.query(models.Profile).filter(
        models.Profile.keycloak_id == keycloak_id, models.Profile.userType == "VENDOR"
    ).first()

    if not db_profile:
        raise HTTPException(
            status_code=404, detail="Vendor profile not found.")

    db.delete(db_profile)
    db.commit()
    await invalidate_profiles_cache()

    return {"message": f"Vendor profile for {keycloak_id} has been deleted."}


@router.get("/admins/{keycloak_id}", response_model=schemas.Profile)
async def get_admin_profile(keycloak_id: str, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)) -> schemas.Profile:
    """
    Retrieve an admin's profile by keycloak_id
    Accessible by: Admin themselves OR superuser
    """
    # Check access rights
    if not check_profile_access(keycloak_id, current_user):
        raise HTTPException(
            status_code=403, detail="You don't have permission to access this profile")

    cached_profile = await get_cached_profiles(keycloak_id, db)
    if cached_profile:
        logging.info(f"Returning cached profile for keycloak_id: {keycloak_id}")
        return cached_profile

    db_profile = db.query(models.Profile).filter(
        models.Profile.keycloak_id == keycloak_id, models.Profile.userType == "ADMIN"
    ).first()

    if not db_profile:
        raise HTTPException(
            status_code=404, detail="Admin profile not found.")

    profile_dict = db_profile.to_dict()
    await cache_profiles_response([db_profile])

    return schemas.Profile.model_validate(profile_dict)


@router.get("/freelancers/{keycloak_id}", response_model=schemas.Profile)
async def get_freelancer_profile(keycloak_id: str, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)) -> schemas.Profile:
    """
    Retrieve a freelancer's profile by keycloak_id
    Accessible by: Freelancer themselves OR admin/superuser
    """
    # Check access rights
    if not check_profile_access(keycloak_id, current_user):
        raise HTTPException(
            status_code=403, detail="You don't have permission to access this profile")

    cached_profile = await get_cached_profiles(keycloak_id, db)
    if cached_profile:
        logging.info(f"Returning cached profile for keycloak_id: {keycloak_id}")
        return cached_profile

    db_profile = db.query(models.Profile).filter(
        models.Profile.keycloak_id == keycloak_id, models.Profile.userType == "FREELANCE"
    ).first()

    if not db_profile:
        raise HTTPException(
            status_code=404, detail="Freelancer profile not found.")

    profile_dict = db_profile.to_dict()
    await cache_profiles_response([db_profile])

    return schemas.Profile.model_validate(profile_dict)


@router.put("/freelancers/{keycloak_id}", response_model=schemas.Profile)
async def update_freelancer_profile(keycloak_id: str, profile_update: schemas.ProfileUpdate, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)) -> schemas.Profile:
    """
    Update a freelancer's profile
    Accessible by: Freelancer themselves OR admin/superuser
    """
    # Check access rights
    if not check_profile_access(keycloak_id, current_user):
        raise HTTPException(
            status_code=403, detail="You don't have permission to update this profile")

    db_profile = db.query(models.Profile).filter(
        models.Profile.keycloak_id == keycloak_id, models.Profile.userType == "FREELANCE"
    ).first()

    if not db_profile:
        raise HTTPException(
            status_code=404, detail="Freelancer profile not found.")

    for key, value in profile_update.model_dump(exclude_none=True).items():
        setattr(db_profile, key, value)

    db.commit()
    db.refresh(db_profile)
    await invalidate_profiles_cache()

    profile_dict = db_profile.to_dict()
    return schemas.Profile.model_validate(profile_dict)


@router.patch("/freelancers/{keycloak_id}", response_model=schemas.Profile)
async def patch_freelancer_profile(keycloak_id: str, profile_patch: schemas.ProfileUpdate, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)) -> schemas.Profile:
    """
    Partially update a freelancer's profile
    Accessible by: Freelancer themselves OR admin/superuser
    """
    # Check access rights
    if not check_profile_access(keycloak_id, current_user):
        raise HTTPException(
            status_code=403, detail="You don't have permission to update this profile")

    db_profile = db.query(models.Profile).filter(
        models.Profile.keycloak_id == keycloak_id, models.Profile.userType == "FREELANCE"
    ).first()

    if not db_profile:
        raise HTTPException(
            status_code=404, detail="Freelancer profile not found.")

    for key, val in profile_patch.model_dump(exclude_none=True).items():
        setattr(db_profile, key, val)

    db.commit()
    db.refresh(db_profile)
    await invalidate_profiles_cache()

    profile_dict = db_profile.to_dict()
    return schemas.Profile.model_validate(profile_dict)


@router.delete("/freelancers/{keycloak_id}", response_model=dict)
async def delete_freelancer_profile(keycloak_id: str, db: Session = Depends(get_db), current_user: schemas.User = Depends(require_roles(["admin", "superuser"]))) -> dict:
    """
    Delete a freelancer's profile
    Accessible by: Admin or Superuser only
    """
    db_profile = db.query(models.Profile).filter(
        models.Profile.keycloak_id == keycloak_id, models.Profile.userType == "FREELANCE"
    ).first()

    if not db_profile:
        raise HTTPException(
            status_code=404, detail="Freelancer profile not found.")

    db.delete(db_profile)
    db.commit()
    await invalidate_profiles_cache()

    return {"message": f"Freelancer profile for {keycloak_id} has been deleted."}

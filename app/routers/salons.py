# app/routers/services.py

from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select
from ..database import SessionLocal, engine
from ..models import Salon
from datetime import datetime
from datetime import datetime as dt

import logging
from .. import models, schemas
from ..utils.cache import get_cached_salons, invalidate_salons_cache, cache_salons_response
from ..services.storage import storage_service
from ..utils.image_processor import image_processor
from ..dependencies import get_current_user

router = APIRouter(
    prefix="/salons",
    tags=["salons"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_salon_open(opening_hours: dict) -> bool:
    """
    Check if a salon is currently open based on its opening hours.
    """
    if not opening_hours:
        return False

    current_time = datetime.now()
    current_day = current_time.strftime("%A")
    current_hour = current_time.time()

    today_hours = opening_hours.get(current_day, {"open": None, "close": None})
    open_time = today_hours.get("open")
    close_time = today_hours.get("close")

    if not open_time or not close_time:
        return False

    open_time = datetime.strptime(open_time, "%H:%M").time()
    close_time = datetime.strptime(close_time, "%H:%M").time()

    return open_time <= current_hour <= close_time


@router.post("/", response_model=schemas.Salon)
async def create_salon(salon_create: schemas.SalonCreate, db: Session = Depends(get_db)) -> schemas.Salon:
    """
    Create a new Salon
    """

    db_salon = models.Salon(**salon_create.dict())
    db.add(db_salon)
    db.commit()
    db.refresh(db_salon)
    await invalidate_salons_cache()
    return db_salon


@router.get("/", response_model=list[schemas.Salon])
async def read_salons(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)) -> list[schemas.Salon]:

    logger.info("Fetching salons with pagination")

    """
    List all Salons
    """

    if limit > 100:
        limit = 100
    if skip < 0:
        skip = 0

    cached_salons = await get_cached_salons(db)
    if cached_salons:
        logger.info("Returning cached salons")
        return cached_salons[skip:skip + limit]

    query = (db.query(models.Salon).options(selectinload(models.Salon.owner) if hasattr(models.Salon, 'owner') else (),
                                            selectinload(models.Salon.services) if hasattr(
                                                models.Salon, 'services') else (),
                                            selectinload(models.Salon.reviews) if hasattr(
                                                models.Salon, 'reviews') else (),
                                            selectinload(models.Salon.staff_member) if hasattr(models.Salon, 'staff_member') else ()))
    query = query.offset(skip).limit(limit)

    results = query.all()
    if not results:
        logger.warning("No salons found in the database")
        raise HTTPException(status_code=404, detail="No salons found")

    serialized_salons = []
    for salon in results:
        serialized_salons.append(
            schemas.Salon(
                salon_id=salon.salon_id,
                name=salon.name,
                description=salon.description,
                image_url=getattr(salon, "image_url", None),
                street=getattr(salon, "street", None),
                city=getattr(salon, "city", None),
                state=getattr(salon, "state", None),
                zip_code=getattr(salon, "zip_code", None),
                country=getattr(salon, "country", None),
                latitude=getattr(salon, "latitude", None),
                longitude=getattr(salon, "longitude", None),
                phone_number=getattr(salon, "phone_number", None),
                website=getattr(salon, "website", None),
                social_media_links=getattr(salon, "social_media_links", None),
                status=getattr(salon, "status", None),
                opening_hours=getattr(salon, "opening_hours", None),
                created_at=getattr(salon, "created_at", None),
                updated_at=getattr(salon, "updated_at", None),
                owner=(
                    {
                        "user_id": salon.owner.user_id,
                        "email": salon.owner.email,
                        "first_name": salon.owner.first_name,
                        "last_name": salon.owner.last_name,
                    } if getattr(salon, "owner", None) else None
                ),
                services=[
                    {
                        "service_id": s.service_id,
                        "name": s.name,
                        "price": s.price,
                        "duration": s.duration
                    } for s in getattr(salon, "services", []) or []
                ],
                reviews=[
                    {
                        "review_id": r.review_id,
                        "rating": getattr(r, "rating", None),
                        "comment": getattr(r, "comment", None)
                    } for r in getattr(salon, "reviews", []) or []
                ],
                staff_member=[
                    {
                        "staff_id": st.staff_id,
                        "first_name": st.first_name,
                        "last_name": st.last_name,
                        "role": st.role,
                        "email": st.email
                    } for st in getattr(salon, "staff_member", []) or []
                ]
            )
        )

    await cache_salons_response(serialized_salons)
    return serialized_salons


@router.get("/{salon_id}", response_model=schemas.Salon)
async def read_salon(salon_id: int, db: Session = Depends(get_db)) -> schemas.Salon:
    """
    Get a specific Salon with ID
    """
    salon = db.query(models.Salon).filter(
        models.Salon.salon_id == salon_id).first()
    if not salon:
        raise HTTPException(status_code=404, detail="Salon not found")
    return salon


@router.put('/{salon_id}', response_model=schemas.Salon)
async def update_salon(salon_id: int, salon_update: schemas.SalonUpdate, db: Session = Depends(get_db)
                       ) -> schemas.SalonBase:
    """
    Update a Salon
    """
    db_salon = db.query(models.Salon).filter(
        models.Salon.salon_id == salon_id).first()
    if not db_salon:
        raise HTTPException(
            status_code=404, detail='Salon was not found')

    for key, val in salon_update.dict(exclude_unset=True).items():
        setattr(db_salon, key, val)

    db.commit()
    db.refresh(db_salon)
    await invalidate_salons_cache()
    return db_salon


@router.delete('/{salon_id}', response_model=dict)
async def delete_service(salon_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    """
    Deletes an Salon
    """
    db_salon = db.query(models.Salon).filter(
        models.Salon.salon_id == salon_id).first()
    if not db_salon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Salon was not found')
    db.delete(db_salon)
    db.commit()
    await invalidate_salons_cache()
    return {'message': 'Salon was succesfully deleted'}


@router.post("/{salon_id}/image", response_model=schemas.SalonImageUploadResponse)
async def upload_salon_image(
    salon_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
) -> schemas.SalonImageUploadResponse:
    """
    Upload or update salon cover image
    Accessible by: Salon owner OR admin/superuser
    """
    # Verify salon exists
    db_salon = db.query(models.Salon).filter(
        models.Salon.salon_id == salon_id
    ).first()

    if not db_salon:
        raise HTTPException(
            status_code=404,
            detail="Salon not found"
        )

    # Check access rights (salon owner or admin)
    if current_user.role not in ["admin", "superuser"]:
        # Check if user is the salon owner
        if not hasattr(db_salon, 'owner_id') or db_salon.owner_id != current_user.user_id:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to upload images for this salon"
            )

    # Validate and process image
    await image_processor.validate_salon_image(file)
    processed_file, ext = await image_processor.process_salon_image(file)

    # Create a temporary UploadFile from processed image
    from fastapi import UploadFile as FastAPIUploadFile
    temp_file = FastAPIUploadFile(
        filename=f"cover.{ext}",
        file=processed_file
    )
    temp_file.content_type = f"image/{ext}"

    # Upload to Spaces
    image_url = await storage_service.upload_salon_image(temp_file, salon_id, "cover")

    # Update database
    db_salon.image_url = image_url
    db.commit()
    db.refresh(db_salon)

    await invalidate_salons_cache()

    return schemas.SalonImageUploadResponse(
        message="Salon image uploaded successfully",
        file_url=image_url,
        uploaded_at=dt.now(),
        salon_id=salon_id,
        image_type="cover"
    )


@router.delete("/{salon_id}/image", response_model=dict)
async def delete_salon_image(
    salon_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
) -> dict:
    """
    Delete salon cover image
    Accessible by: Salon owner OR admin/superuser
    """
    # Verify salon exists
    db_salon = db.query(models.Salon).filter(
        models.Salon.salon_id == salon_id
    ).first()

    if not db_salon:
        raise HTTPException(
            status_code=404,
            detail="Salon not found"
        )

    # Check access rights
    if current_user.role not in ["admin", "superuser"]:
        if not hasattr(db_salon, 'owner_id') or db_salon.owner_id != current_user.user_id:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to delete images for this salon"
            )

    if not db_salon.image_url:
        raise HTTPException(
            status_code=404,
            detail="No image found for this salon"
        )

    # Delete from Spaces
    deleted = await storage_service.delete_salon_image(
        salon_id,
        db_salon.image_url
    )

    if deleted:
        # Update database
        db_salon.image_url = None
        db.commit()
        await invalidate_salons_cache()

        return {"message": "Salon image deleted successfully"}
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to delete salon image from storage"
        )

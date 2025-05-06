# app/routers/services.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..database import SessionLocal, engine
from ..models import Salon
from datetime import datetime

import logging
from .. import models, schemas
from ..utils.cache import get_cached_salons, invalidate_salons_cache, cache_salons_response

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
    
    query = ( db.query(models.Salon)
        .offset(skip)
        .limit(limit))
    
    results = query.all()
    if not results:
        logger.warning("No salons found in the database")
        raise HTTPException(status_code=404, detail="No salons found")
    serialized_salons = [
        schemas.Salon(
            salon_id=salon.salon_id,
            name=salon.name,
            description=salon.description,
            image_url=salon.image_url,
            owner_id=salon.owner_id,
            street=salon.street,
            city=salon.city,
            state=salon.state,
            zip_code=salon.zip_code,
            country=salon.country,
            created_at=salon.created_at,
            updated_at=salon.updated_at,
            owner=salon.owner.to_dict() if salon.owner else None,
            services=[service.to_dict() for service in salon.services],
            reviews=[review.to_dict() for review in salon.reviews],
            staff_member=[staff.to_dict() for staff in salon.staff_member]
        ) for salon in results
    ]

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
    db_salon = db.query(models.Salon).filter(models.Salon.salon_id == salon_id).first()
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
    db_salon = db.query(models.Salon).filter(models.Salon.salon_id == salon_id).first()
    if not db_salon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Salon was not found')
    
    db.delete(db_salon)
    db.commit()
    await invalidate_salons_cache()
    return {'message': 'Salon was succesfully deleted'}

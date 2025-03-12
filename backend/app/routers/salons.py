# app/routers/services.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..database import SessionLocal, engine
from ..models import Salon
from .. import models, schemas
from ..utils.cache import get_cached_salons, invalidate_cache

router = APIRouter(
    prefix="/salons",
    tags=["salons"],
    responses={404: {"description": "Not found"}},
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=schemas.Salon)
async def create_salon(salon_create: schemas.SalonCreate, db: Session = Depends(get_db)) -> schemas.Salon:
    """
    Create a new Salon
    """

    db_salon = models.Salon(
        name=salon_create.name,
        description=salon_create.description,
        image_url=salon_create.image_url,
        owner_id=salon_create.owner_id,
        street=salon_create.street,
        city=salon_create.city or "Dar Es Salaam",
        state=salon_create.state,
        zip_code=salon_create.zip_code,
        country=salon_create.country
    )
    db.add(db_salon)
    db.commit()
    db.refresh(db_salon)
    # await invalidate_cache("salons:*")
    return db_salon


@router.get("/", response_model=list[schemas.Salon])
async def read_salons(db: Session = Depends(get_db)) -> list[schemas.Salon]:
    """
    List all Salons
    """
    salons = await get_cached_salons(db)
    return salons


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


@router.put('/{salon_id}')
async def update_salon(salon_id: int, salon_update: schemas.SalonUpdate, db: Session = Depends(get_db)
                       ) -> schemas.SalonBase:
    """
    Update a Salon
    """
    db_salon = db.get(models.Salon, salon_id)
    if db_salon is None:
        raise HTTPException(
            status_code=404, detail='Salon was not found')

    for key, val in salon_update.model_dump(exclude_none=True).items():
        setattr(db_salon, key, val)

    db.commit()
    db.refresh(db_salon)
    # await invalidate_cache(f"salons:{salon_id}")

    return db_salon


@router.delete('/{salon_id}')
async def delete_service(salon_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    """
    Deletes an Salon
    """
    db_salon = db.get(models.Salon, salon_id)
    db.delete(db_salon)
    db.commit()
    # await invalidate_cache("salons:*")
    return {'message': 'Salon was succesfully deleted'}

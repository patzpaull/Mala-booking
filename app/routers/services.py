# app/routers/services.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
# from sqlalchemy import select
from ..database import SessionLocal, engine
# from ..models import Service
from .. import models, schemas
import logging
from ..utils.cache import get_cached_service, invalidate_services_cache, cache_services_response


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/services",
    tags=["services"],
    responses={404: {"description": "Not found"}},
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=schemas.Service)
async def create_service(service: schemas.ServiceCreate, db: Session = Depends(get_db)) -> schemas.Service:
    """
    Create a new Service
    """

    db_service = models.Service(**service.model_dump())
    db.add(db_service)
    db.commit()
    db.refresh(db_service)
    await invalidate_services_cache()
    return db_service


@router.get("/", response_model=list[schemas.Service])
async def read_services(skip: int = 0,
                        limit: int = 100,
                        db: Session = Depends(get_db)
                        ) -> list[schemas.Service]:
    
    logger.info("Fetching services with pagination")
    """
    List all Services
    """

# Validate Pagination parameters
    if limit > 100:
        limit = 100
    if skip < 0:
        skip = 0

    cached_services = await get_cached_service(db)
    if cached_services:
        logger.info("Returning cached services")
        return cached_services[skip:skip + limit]
    
    query = (db.query(models.Service).offset(skip).limit(limit))

    results = query.all()

    if not results:
        logger.warning("No Services Found")
        raise HTTPException(status_code=404, detail="No Services Found")

    serialized_services = [
        schemas.Service(
            service_id=service.service_id,
            name=service.name,
            description=service.description,
            duration=service.duration,
            price=service.price,
            salon_id=service.salon_id,
            created_at=service.created_at,
            updated_at=service.updated_at,
        )
        for service in results
    ]

    await cache_services_response(serialized_services)

    return serialized_services


@router.get("/{service_id}", response_model=schemas.Service)
async def read_service(service_id: int, db: Session = Depends(get_db)) -> schemas.Service:
    """
    Get a specific Service with ID
    """
    service = db.query(models.Service).filter(models.Service.service_id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.put('/{service_id}', response_model=schemas.Service)
async def update_service(service_id: int, service_update: schemas.ServiceUpdate, db: Session = Depends(get_db)
                         ) -> schemas.Service:
    """
    Update a Service
    """
    db_service = db.query(models.Service).filter(models.Service.service_id == service_id).first()
    if not db_service:
        raise HTTPException(status_code=404, detail='Service was not found')

    for key, val in service_update.model_dump(exclude_none=True).items():
        setattr(db_service, key, val)

    db.commit()
    db.refresh(db_service)
    await invalidate_services_cache()
    return db_service


@router.delete('/{service_id}')
async def delete_service(service_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    """
    Deletes an Service
    """
    db_service = db.get(models.Service).filter(models.Service.service_id == service_id).first()
    if not db_service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Service was not found')
    
    db.delete(db_service)
    db.commit()
    await invalidate_services_cache()
    return {'message': 'Service succesfully deleted'}

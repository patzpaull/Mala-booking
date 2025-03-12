# app/routers/services.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..database import SessionLocal, engine
from ..models import Service
from .. import models, schemas
# from app.dependencies import verify_token
from ..utils.cache import get_cached_service, invalidate_cache


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
    # await invalidatiimete_cache("services:*")
    return db_service


@router.get("/")
async def read_services(db: Session = Depends(get_db)
                        ) -> list[schemas.Service]:
    """
    List all Services
    """
    services = await get_cached_service(db)

    return services


@router.get("/{service_id}", response_model=schemas.Service)
async def read_service(service_id: int, db: Session = Depends(get_db)) -> schemas.Service:
    """
    Get a specific Service with ID
    """
    service = await get_cached_service(db)
    service = next((u for u in service if u["service_id"] == service_id), None)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.put('/{service_id}')
async def update_service(service_id: int, services: schemas.ServiceUpdate, db: Session = Depends(get_db)
                         ) -> schemas.Service:
    """
    Update a Service
    """
    db_service = db.get(models.Service, service_id)
    if db_service is None:
        raise HTTPException(
            status_code=404, detail='Service was not found')

    for key, val in services.model_dump(exclude_none=True).items():
        setattr(services, key, val)

    db.commit()
    db.refresh(db_service)
    # await invalidate_cache(f"service:{service_id}")

    return db_service


@router.delete('/{service_id}')
async def delete_service(service_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    """
    Deletes an Service
    """
    db_service = db.get(models.Service, service_id)
    db.delete(db_service)
    db.commit()
    # await invalidate_cache(f"service:*")
    return {'message': 'Service succesfully deleted'}

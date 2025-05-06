# app/routers/appointments.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..database import SessionLocal, engine
# from ..models import Appointment
from .. import models, schemas
import logging
from ..utils.cache import get_cached_appointments, invalidate_appointments_cache, cache_appointments_response

router = APIRouter(
    prefix="/appointments",
    tags=["appointments"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)
# Dependency to get DB session


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



@router.post('/', response_model=schemas.Appointment)
async def create_appointment(appointment: schemas.AppointmentCreate, db: Session = Depends(get_db)
                             ) -> schemas.Appointment:
    """
    Create a new Appointment
    """

    db_appointment = models.Appointment(**appointment.model_dump())
    db.add(db_appointment)
    db.commit()
    db.refresh(db_appointment)
    return db_appointment  


@router.get('/', response_model=list[schemas.AppointmentBase])
async def read_appointments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)) -> list[schemas.AppointmentBase]:
    """
    List all Appointments
    """
    if limit > 100:
        limit = 100
    if skip < 0:
        skip = 0

    cached_appointments = await get_cached_appointments(db)
    if cached_appointments:
        logger.info("Returning cached appointments")
        return cached_appointments[skip:skip + limit]
    

    query = (db.query(models.Appointment).offset(skip).limit(limit))

    results = query.all()

    if not results:
        logger.warning("No Appointments found")
        raise HTTPException(status_code=404, detail="No appointments found")

    serialized_appointments = [
        schemas.Appointment(
            appointment_id = appointment.appointment_id,
            appointment_time=appointment.appointment_time,
            duration=appointment.duration,
            notes=appointment.notes,
            client_id = appointment.client_id,
            service_id = appointment.service_id,    
            reminder_time= appointment.reminder_time,
            staff_id = appointment.staff_id, 
            status = appointment.status, 
            created_at = appointment.created_at,
            updated_at= appointment.updated_at,
        ) for appointment in results
    ]

    await cache_appointments_response(serialized_appointments)

    return serialized_appointments


@router.get('/{appointment_id}', response_model=schemas.Appointment)
async def read_appointment(appointment_id: int, db: Session = Depends(get_db)
                           ) -> schemas.Appointment:
    """
    Get Specific Appointment with ID 
    """
    # user_id = token_payload.get("sub")
    # roles = token_payload.get('realm_access', {}).get('roles', [])

    appointment = db.query(models.Appointment).filter(models.Appointment.appointment_id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not Found")
    return appointment

@router.put('/{appointment_id}', response_model=schemas.Appointment)
async def update_appointment(appointment_id: int, appointment_update: schemas.AppointmentUpdate, db: Session = Depends(get_db)
                             ) -> schemas.Appointment:
    """
    Update an Appointment
    """

    db_appointment = db.query(models.Appointment).filter(models.Appointment.appointment_id == appointment_id).first()

    if not db_appointment:
        raise HTTPException(
            status_code=404, detail='Appointment was not found')
    for key, val in appointment_update.dict(exclude_unset=True).items():
        setattr(db_appointment, key, val)

    db.commit()
    db.refresh(db_appointment)
    await invalidate_appointments_cache()
    return db_appointment


@router.delete('/{appointment_id}')
async def delete_appointment(appointment_id: int, db: Session = Depends(get_db)):
    """
    Deletes an Appointment
    """

    db_appointment = db.query(models.Appointment).filter(
        models.Appointment.appointment_id == appointment_id
    ).first()

    if not db_appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    db.delete(db_appointment)
    db.commit()
    await invalidate_appointments_cache()
    return {'message': 'Appointment succesfully deleted'}

# app/routers/appointments.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..database import SessionLocal, engine
from ..models import Appointment
from .. import models, schemas

router = APIRouter(
    prefix="/appointments",
    tags=["appointments"],
    responses={404: {"description": "Not found"}},
)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get('/appointments')
async def read_appointments(skip: int = 0, limit: int = 15, db: Session = Depends(get_db)
) -> list[schemas.Appointment]:
    """
    List all Items
    """
    appointments = db.execute(select(models.Appointment)).scalars().all()
    # appointments = db.query(models.Appointment).offset(skip).limit(limit).all()
    return appointments

@router.post('/appointments')
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

@router.get('/appointments/{appointment_id}')
async def update_appointment(appointment_id: int, appointments:schemas.AppointmentUpdate, db:Session = Depends(get_db)
)-> schemas.Appointment:
    """
    Update Appointment
    """
    db_appointment = db.get(models.Appointment, appointment_id)
    if db_appointment is None:
        raise HTTPException(status_code=404, detail='Item not found')
    
    for key,val in appointments.model_dump(exclude_none=True).items():
        setattr(appointments, key, val)
    
    db.commit()
    db.refresh(appointments)
    
    return appointments

@router.delete('/appointments/{appointment_id}')
async def delete_appointment( appointment_id: int,db: Session = Depends(get_db)) -> dict[str,str]:
    """
    Deletes an Appointment
    """
    db_appointment = db.get(models.Appointment, appointment_id)
    db.delete(db_appointment)
    db.commit()
    return {'message':'Item succesfully deleted'}
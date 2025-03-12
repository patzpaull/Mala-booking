# app/routers/appointments.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..database import SessionLocal, engine
from ..models import Appointment
from .. import models, schemas
# from app.dependencies import verify_token

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


@router.get('/')
async def read_appointments(db: Session = Depends(get_db)
                            ) -> list[schemas.AppointmentBase]:
    """
    List all Appointments
    """
    # user_id = payload.get('sub')
    # roles= payload.get('realm_acess', {}).get('roles',[])

    # if 'ADMIN' in roles:
    # appointments = db.query(models.Appointment).scalar().all()
    # elif 'CUSTOMER' in roles:
    # appointments = db.query(models.Appointment).filter(models.Appointment.client_id == user_id).all()
    # elif 'VENDOR' in roles:
    # appointments = db.query(models.Appointment).filter(models.Appointment.staff_id == user_id).all()
    # else:
    # raise HTTPException(
    # status_code =status.HTTP_403_FORBIDDEN,
    # detail="Insufficient permissions"
    # )

    appointments = db.execute(select(models.Appointment)).scalars().all()

    return appointments


@router.get('/{appointment_id}', response_model=schemas.Appointment)
async def read_appointment(appointment_id: int, db: Session = Depends(get_db)
                           ) -> schemas.Appointment:
    """
    Get Specific Appointment with ID 
    """
    # user_id = token_payload.get("sub")
    # roles = token_payload.get('realm_access', {}).get('roles', [])

    appointment = db.query(models.Appointment).filter(
        models.Appointment.appointment_id == appointment_id).first()
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not Found")

     # Authorization check
    # if 'ADMIN' in roles:
        # Admin can access any appointment
    appointment = db.query(models.Appointment).all()

    # pass
    # elif 'CUSTOMER' in roles:
    # appointment = db.query(models.Appointment).all()

    # if appointment.client_id != user_id:
    # raise HTTPException(
    # status_code=status.HTTP_403_FORBIDDEN,
    # detail="You can only access your own appointments"
    # )
    # elif 'VENDOR' in roles:
    # appointment = db.query(models.Appointment).filter(
    # models.Appointment.staff_id == user_id).all()
    # if appointment.staff_id != user_id:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="You can only access appointments assigned to you"
    #     )
    # elif 'FREELANCE' in roles:
    # appointment = db.query(models.Appointment).filter(
    # models.Appointment.staff_id == user_id).all()

    return appointment


@router.post('/', response_model=schemas.Appointment)
async def create_appointment(appointment: schemas.AppointmentCreate, db: Session = Depends(get_db)
                             ) -> schemas.Appointment:
    """
    Create a new Appointment
    """

    db_appointment = models.Appointment(
        appointment_time=appointment.appointment_time,
        duration=appointment.duration,
        client_id=appointment.client_id,
        service_id=appointment.service_id,
        staff_id=appointment.staff_id,
        notes=appointment.notes,
        reminder_time=appointment.reminder_time,
        status=appointment.status or "pending",
    )
    db.add(db_appointment)
    db.commit()
    db.refresh(db_appointment)
    return db_appointment


@router.put('/{appointment_id}', response_model=schemas.Appointment)
async def update_appointment(appointment_id: int, appointment_update: schemas.AppointmentUpdate, db: Session = Depends(get_db)
                             ) -> schemas.Appointment:
    """
    Update an Appointment
    """

    # token_payload = {}  # Define or import token_payload appropriately

    # db_appointment = db.get(models.Appointment, appointment_id)
    db_appointment = db.query(models.Appointment).filter(
        models.Appointment.appointment_id == appointment_id).first()

    if db_appointment is None:
        raise HTTPException(
            status_code=404, detail='Appointment was not found')

    #  # Authorization check
    # if 'admin' in roles:
    #     pass  # Admin can update any appointment
    # elif 'client' in roles:
    #     if db_appointment.client_id != user_id:
    #         raise HTTPException(
    #             status_code=status.HTTP_403_FORBIDDEN,
    #             detail="You can only update your own appointments"
    #         )
    # elif 'vendor' in roles:
    #     if db_appointment.staff_id != user_id:
    #         raise HTTPException(
    #             status_code=status.HTTP_403_FORBIDDEN,
    #             detail="You can only update appointments assigned to you"
    #         )
    # else:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Insufficient permissions to update appointments"
        # )

    for key, val in appointment_update.model_dump(exclude_none=True).items():
        setattr(db_appointment, key, val)

    db.commit()
    db.refresh(db_appointment)

    return db_appointment


@router.delete('/{appointment_id}')
async def delete_appointment(appointment_id: int, db: Session = Depends(get_db)):
    """
    Deletes an Appointment
    """

    # user_id = token_payload.get('sub')
    # roles = token_payload.get('realm_access', {}).get('roles', [])

    db_appointment = db.query(models.Appointment).filter(
        models.Appointment.appointment_id == appointment_id
    ).first()

    if db_appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # # Authorization check
    # if 'admin' in roles:
    #     pass  # Admin can delete any appointment
    # elif 'client' in roles:
    #     if db_appointment.client_id != user_id:
    #         raise HTTPException(
    #             status_code=status.HTTP_403_FORBIDDEN,
    #             detail="You can only delete your own appointments"
    #         )
    # elif 'vendor' in roles:
    #     if db_appointment.staff_id != user_id:
    #         raise HTTPException(
    #             status_code=status.HTTP_403_FORBIDDEN,
    #             detail="You can only delete appointments assigned to you"
    #         )
    # else:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Insufficient permissions to delete appointments"
    #     )

    db.delete(db_appointment)
    db.commit()
    return {'message': 'Appointment succesfully deleted'}

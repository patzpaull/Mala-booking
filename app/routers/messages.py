# app/routers/messages.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import time
from typing import List

from .. import models, schemas
from ..database import get_db
from ..dependencies import get_current_user

router = APIRouter(
    prefix="/appointments/{appointment_id}/messages",
    tags=["messages"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", response_model=schemas.Message)
async def send_message(
    appointment_id: int,
    message_create: schemas.MessageCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Send a message related to an appointment.
    """
    # Ensure appointment exists
    appointment = db.query(models.Appointment).filter(
        models.Appointment.appointment_id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Authorization check: Sender must be either the client or a staff member
    # if current_user.user_id not in (appointment.client_id, appointment.staff_id):
        # raise HTTPException(
        # status_code=status.HTTP_403_FORBIDDEN,
        # detail="Not authorized to send messages for this appointment"
        # )

    db_message = models.Message(
        sender_id=current_user.user_id,
        receiver_id=message_create.receiver_id,
        appointment_id=appointment_id,
        message_text=message_create.message_text,
        sent_time=time.utcnow()
    )

    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message


@router.get("/", response_model=List[schemas.Message])
def get_messages(
    appointment_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all messages for a specific appointment.
    """
    # Ensure appointment exists
    appointment = db.query(models.Appointment).filter(
        models.Appointment.appointment_id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # # Authorization check
    # if current_user.user_id not in (appointment.client_id, appointment.staff_id):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Not authorized to view messages for this appointment"
    #     )

    messages = db.query(models.Message).filter(
        models.Message.appointment_id == appointment_id
    ).all()
    return messages

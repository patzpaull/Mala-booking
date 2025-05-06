# app/routers/payments.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..database import SessionLocal, engine
from ..models import Payment
from .. import models, schemas

router = APIRouter(
    prefix="/payments",
    tags=["payments"],
    responses={404: {"description": "Not found"}},
)

# Dependency to get DB session


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Listing all payments


@router.get('/')
async def read_payments(skip: int = 0, limit: int = 15, db: Session = Depends(get_db)
                        ) -> list[schemas.Payment]:
    """
    List all Payments
    """
    payments = db.execute(select(models.Appointment)).scalars().all()
    # appointments = db.query(models.Appointment).offset(skip).limit(limit).all()
    return payments


@router.get('/{payment_id}')
async def read_payment(payment_id: int, db: Session = Depends(get_db)
                       ) -> schemas.Appointment:
    """
    Get Specific Payment with ID 
    """
    payment = db.query(models.Payment).filter(
        models.Payment.payment_id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not Found")
    return payment


@router.post('/')
async def create_appointment(payment: schemas.PaymentCreate, db: Session = Depends(get_db)
                             ) -> schemas.Payment:
    """
    Generate a new payment 
    """
    db_payment = models.Payment(**payment.model_dump())
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment


@router.delete('/{payment_id}')
async def delete_payment(payment_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    """
    Deletes payment infoAppointment
    """
    db_payment = db.get(models.Payment, payment_id)
    db.delete(payment_id)
    db.commit()
    return {'message': 'Payment succesfully deleted'}

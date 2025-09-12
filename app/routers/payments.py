# app/routers/payments.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..database import get_db
from ..models import Payment
from .. import models, schemas

router = APIRouter(
    prefix="/payments",
    tags=["payments"],
    responses={404: {"description": "Not found"}},
)

# Dependency to get DB session



# Listing all payments


@router.get('/')
async def read_payments(skip: int = 0, limit: int = 15, db: Session = Depends(get_db)
                        ) -> list[schemas.Payment]:
    """
    List all Payments
    """
    payments = db.execute(select(models.Payment)).scalars().all()
    return [schemas.Payment.model_validate(payment.to_dict()) for payment in payments]


@router.get('/{payment_id}')
async def read_payment(payment_id: int, db: Session = Depends(get_db)
                       ) -> schemas.Payment:
    """
    Get Specific Payment with ID 
    """
    payment = db.query(models.Payment).filter(
        models.Payment.payment_id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not Found")
    return schemas.Payment.model_validate(payment.to_dict())


@router.post('/')
async def create_payment(payment: schemas.PaymentCreate, db: Session = Depends(get_db)
                         ) -> schemas.Payment:
    """
    Generate a new payment 
    """
    db_payment = models.Payment(**payment.model_dump())
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return schemas.Payment.model_validate(db_payment.to_dict())


@router.delete('/{payment_id}')
async def delete_payment(payment_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    """
    Deletes payment info
    """
    db_payment = db.get(models.Payment, payment_id)
    if not db_payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    db.delete(db_payment)
    db.commit()
    return {'message': 'Payment successfully deleted'}

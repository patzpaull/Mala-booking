# app/routers/staffs.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..database import SessionLocal, engine
from ..models import Staff
from .. import models, schemas
from ..utils.cache import get_cached_staff, invalidate_cache

router = APIRouter(
    prefix="/staff",
    tags=["staff"],
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
async def read_staff(skip: int = 0, limit: int = 15, db: Session = Depends(get_db)
                     ) -> list[schemas.Staff]:
    """
    List all Staff workers
    """
    staff = await get_cached_staff(db)
    if not staff:
        raise HTTPException(status_code=404, detail="No staff Members found")
    # appointments = db.query(models.Appointment).offset(skip).limit(limit).all()
    return staff[skip:skip + limit]


@router.get('/{staff_id}')
async def read_staff_member(staff_id: int, db: Session = Depends(get_db)
                            ) -> schemas.Staff:
    """
    Get Specific Staff Member with ID 
    """
    staff_member = await get_cached_staff(db)
    staff_member = next(
        (u for u in staff_member if u["staff_id"] == staff_id), None)
    if not staff_member:
        raise HTTPException(status_code=404, detail="Staff not Found")
    return staff_member


@router.get('/salon/{salon_id}')
async def read_staff_by_salon(salon_id: int, db: Session = Depends(get_db)
                              ) -> list[schemas.Staff]:
    """
    Get Specific Staff Member Belonging to specific salon by salon_ID 
    """
    staff_member = await get_cached_staff(db)
    # staff_member
    if not staff_member:
        raise HTTPException(
            status_code=404, detail="No staff for this salon Found")
    return staff_member


@router.post('/')
async def create_staff(staff_create: schemas.StaffCreate, db: Session = Depends(get_db)
                       ) -> schemas.StaffCreate:
    """
    Create Staff User
    """
    # db_staffie = db.query(models.Staff).filter(
    #     models.Staff.email == Staff.email).first()
    # if db_staffie:
    #     raise HTTPException(status_code=400, detail="Email already registered")

    db_staff = models.Staff(
        user_id=staff_create.user_id,
        salon_id=staff_create.salon_id,
        email=staff_create.email,
        first_name=staff_create.first_name,
        last_name=staff_create.last_name,
        role=staff_create.role or "Stylist")
    db.add(db_staff)
    db.commit()
    db.refresh(db_staff)

    # await invalidate_cache("staffs:*")
    return db_staff


@router.put('/{staff_id}')
async def update_staff(staff_id: int, staff_update: schemas.StaffUpdate, db: Session = Depends(get_db)
                       ) -> schemas.Staff:
    """
    Update staff info
    """
    db_staff = db.get(models.Staff, staff_id)
    if db_staff is None:
        raise HTTPException(
            status_code=404, detail='Staff was not found')

    for key, val in staff_update.model_dump(exclude_none=True).items():
        setattr(db_staff, key, val)

    db.commit()
    db.refresh(db_staff)

    # await invalidate_cache(f"staffs:{staff_id}")
    return db_staff


@router.delete('/{staff_id}')
async def delete_staff(staff_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    """
    Deletes Staff info
    """
    db_staff = db.query(models.Staff).filter(
        models.Staff.staff_id == staff_id).first()
    if not db_staff:
        raise HTTPException(status_code=404, detail="Staff Member not found")

    db.delete(db_staff)
    db.commit()
    # await invalidate_cache("staffs:*")
    return {'message': 'Staff Info succesfully deleted'}


@router.delete('/salon/{salon_id}')
async def delete_staff(salon_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    """
    Deletes all staff from a particular saloon
    """
    db_staffs = db.query(models.Staff).filter(
        models.Staff.salon_id == salon_id).all()
    if not db_staffs:
        raise HTTPException(
            status_code=404, detail="Salon's Staff Members not found")

    for db_staff in db_staffs:
        db.delete(db_staff)

    db.commit()
    # await invalidate_cache("staffs:*")
    return {'message': f'All Staff members for salon {salon_id} were succesfully deleted'}

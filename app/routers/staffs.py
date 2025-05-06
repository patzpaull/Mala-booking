# app/routers/staffs.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import SessionLocal
import logging
from .. import models, schemas
from ..utils.cache import get_cached_staff, invalidate_staffs_cache, cache_staffs_response

router = APIRouter(
    prefix="/staff",
    tags=["staff"],
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

# Listing all payments


@router.get('/', response_model=schemas.Staff)
async def read_staff(skip: int = 0, limit: int = 15, db: Session = Depends(get_db)
                     ) -> list[schemas.Staff]:

    logger.info("Fetching staff members from database")
    """
    List all Staff workers
    """

    if limit > 100:
        limit = 100
    if skip < 0:
        skip = 0

    cached_staff = await get_cached_staff(db)
    if cached_staff:
        logger.info("Returning cached staff members")
        return cached_staff[skip:skip + limit]

    query = (
        db.query(models.Staff)
        .offset(skip)
        .limit(limit)
    )

    results = query.all()

    if not results:
        logger.warning("No staff members found")
        raise HTTPException(status_code=404, detail="No staff members found")

    serialized_staff = [
        schemas.Staff(
            staff_id=staff.staff_id,
            user_id=staff.user_id,
            salon_id=staff.salon_id,
            first_name=staff.first_name,
            last_name=staff.last_name,
            email=staff.email,
            phone_number=staff.phone_number,
            role=staff.role,
            created_at=staff.created_at,
            updated_at=staff.updated_at
        ) for staff in results
    ]

    await cache_staffs_response(serialized_staff)

    return serialized_staff


@router.get('/{staff_id}', response_model=schemas.Staff)
async def read_staff_member(staff_id: int, db: Session = Depends(get_db)
                            ) -> schemas.Staff:
    """
    Get Specific Staff Member with ID 
    """

    staff_member = db.query(models.Staff).filter(
        models.Staff.staff_id == staff_id).first()
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


@router.post('/', response_model=schemas.StaffCreate)
async def create_staff(staff_create: schemas.StaffCreate, db: Session = Depends(get_db)
                       ) -> schemas.StaffCreate:
    """
    Create Staff User
    """
    db_staff = models.Staff(**staff_create.model_dump())
    db.add(db_staff)
    db.commit()
    db.refresh(db_staff)
    await invalidate_staffs_cache()
    return db_staff


@router.put('/{staff_id}')
async def update_staff(staff_id: int, staff_update: schemas.StaffUpdate, db: Session = Depends(get_db)
                       ) -> schemas.Staff:
    """
    Update staff info
    """
    db_staff = db.query(models.Staff).filter(
        models.Staff.staff_id == staff_id).first()
    if not db_staff:
        raise HTTPException(
            status_code=404, detail='Staff was not found')

    for key, val in staff_update.model_dump(exclude_unset=True).items():
        setattr(db_staff, key, val)

    db.commit()
    db.refresh(db_staff)
    await invalidate_staffs_cache()
    return db_staff


@router.delete('/{staff_id}', response_model=dict)
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
    await invalidate_staffs_cache()
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
    await invalidate_staffs_cache()
    return {'message': f'All Staff members for salon {salon_id} were succesfully deleted'}

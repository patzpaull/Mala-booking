from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from ..database import SessionLocal
import logging
from typing import List
from .. import models, schemas
from ..utils.cache import get_cached_staff, invalidate_staffs_cache, cache_staffs_response

router = APIRouter(
    prefix="/staff",
    tags=["staff"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get('/', response_model=List[schemas.Staff])
async def read_staff(skip: int = 0, limit: int = 15, db: Session = Depends(get_db)
                     ) -> List[schemas.Staff]:
    logger.info("Fetching staff members from database")

    if limit > 100:
        limit = 100
    if skip < 0:
        skip = 0

    cached_staff = await get_cached_staff(db)
    if cached_staff:
        logger.info("Returning cached staff members")
        # cached_staff may be a list of dicts or ORM objects
        return cached_staff[skip:skip + limit]

    query = (
        db.query(models.Staff)
        .options(selectinload(models.Staff.salon), selectinload(models.Staff.user))
        .order_by(models.Staff.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    results = query.all()

    if not results:
        logger.warning("No staff members found")
        raise HTTPException(status_code=404, detail="No staff members found")

    # await cache_staffs_response(results, db)
    return results


@router.get('/{staff_id}', response_model=schemas.Staff)
async def read_staff_member(staff_id: int, db: Session = Depends(get_db)
                            ) -> schemas.Staff:
    staff_member = (
        db.query(models.Staff)
        .options(selectinload(models.Staff.user), selectinload(models.Staff.salon))
        .filter(models.Staff.staff_id == staff_id)
        .first()
    )
    if not staff_member:
        raise HTTPException(status_code=404, detail="Staff not Found")
    return staff_member


@router.get('/salon/{salon_id}', response_model=List[schemas.Staff])
async def read_staff_by_salon(salon_id: int, db: Session = Depends(get_db)
                              ) -> List[schemas.Staff]:
    cached = await get_cached_staff(db)
    if cached:
        if len(cached) and isinstance(cached[0], dict):
            filtered = [s for s in cached if s.get("salon_id") == salon_id]
        else:
            filtered = [s for s in cached if getattr(
                s, "salon_id", None) == salon_id]
        if filtered:
            return filtered

    results = (
        db.query(models.Staff)
        .options(selectinload(models.Staff.user), selectinload(models.Staff.salon))
        .filter(models.Staff.salon_id == salon_id)
        .all()
    )
    if not results:
        raise HTTPException(
            status_code=404, detail="Staff not Found for this salon")
    return results


@router.post('/', response_model=schemas.Staff, status_code=201)
async def create_staff(staff_create: schemas.StaffCreate, db: Session = Depends(get_db)
                       ) -> schemas.Staff:
    db_staff = models.Staff(**staff_create.model_dump())
    db.add(db_staff)
    db.commit()
    db.refresh(db_staff)
    await invalidate_staffs_cache()
    return db_staff


@router.put('/{staff_id}', response_model=schemas.Staff)
async def update_staff(staff_id: int, staff_update: schemas.StaffUpdate, db: Session = Depends(get_db)
                       ) -> schemas.Staff:
    db_staff = db.query(models.Staff).filter(
        models.Staff.staff_id == staff_id).first()
    if not db_staff:
        raise HTTPException(status_code=404, detail='Staff was not found')

    for key, val in staff_update.model_dump(exclude_unset=True).items():
        setattr(db_staff, key, val)

    db.commit()
    db.refresh(db_staff)
    await invalidate_staffs_cache()
    return db_staff


@router.delete('/{staff_id}', response_model=dict)
async def delete_staff(staff_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    db_staff = db.query(models.Staff).filter(
        models.Staff.staff_id == staff_id).first()
    if not db_staff:
        raise HTTPException(status_code=404, detail="Staff Member not found")

    db.delete(db_staff)
    db.commit()
    await invalidate_staffs_cache()
    return {'message': 'Staff Info succesfully deleted'}


@router.delete('/salon/{salon_id}', response_model=dict)
async def delete_staff_by_salon(salon_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    db_staffs = db.query(models.Staff).filter(
        models.Staff.salon_id == salon_id).all()
    if not db_staffs:
        raise HTTPException(
            status_code=404, detail="Salon's Staff Members not found")

    for db_staff in db_staffs:
        db.delete(db_staff)

    db.commit()
    await invalidate_staffs_cache()
    return {'message': f'All Staff Members for salon {salon_id} successfully deleted'}

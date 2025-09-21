from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from ..database import get_db
from .. import models, schemas
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from ..utils.responses import success_response
from ..dependencies import get_current_user, require_roles
from ..routers.audit import log_admin_action

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/users")
async def get_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    role: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "superuser"])),
    request: Request = None
):
    """
    Get all users with filtering and pagination - required by technical specs
    """
    # Join User and Profile tables for comprehensive user data
    query = db.query(models.User).join(
        models.Profile, models.User.keycloak_id == models.Profile.keycloak_id
    ).add_columns(
        models.Profile.userType,
        models.Profile.firstName,
        models.Profile.lastName,
        models.Profile.status,
        models.Profile.phone_number,
        models.Profile.address
    )
    
    # Apply filters
    if role:
        query = query.filter(models.Profile.userType == role.upper())
        
    if status:
        query = query.filter(models.Profile.status == status.upper())
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            func.or_(
                models.User.first_name.ilike(search_filter),
                models.User.last_name.ilike(search_filter),
                models.User.email.ilike(search_filter),
                models.User.username.ilike(search_filter)
            )
        )
    
    # Get total count for pagination
    total = query.count()
    
    # Apply pagination and ordering
    users = query.order_by(models.User.created_at.desc()).offset(skip).limit(limit).all()
    
    # Format results
    result = []
    for user, user_type, first_name, last_name, profile_status, phone, address in users:
        user_dict = user.to_dict()
        user_dict.update({
            "profile": {
                "userType": user_type,
                "firstName": first_name,
                "lastName": last_name,
                "status": profile_status,
                "phone_number": phone,
                "address": address
            }
        })
        result.append(user_dict)
    
    # Log admin action
    await log_admin_action(
        db=db,
        admin_id=current_user.user_id,
        action="VIEW",
        resource_type="USERS",
        details={"filters": {"role": role, "status": status, "search": search}},
        request=request
    )
    
    return success_response(
        data={
            "users": result,
            "total": total,
            "skip": skip,
            "limit": limit
        },
        message="Users retrieved successfully"
    )

@router.get("/users/{user_id}")
async def get_user_details(
    user_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "superuser"])),
    request: Request = None
):
    """
    Get detailed user information - required by technical specs
    """
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    profile = db.query(models.Profile).filter(
        models.Profile.keycloak_id == user.keycloak_id
    ).first()
    
    # Get user's appointments
    appointments = db.query(models.Appointment).filter(
        models.Appointment.client_id == user_id
    ).count()
    
    # Get user's salons (if vendor)
    salons = db.query(models.Salon).filter(
        models.Salon.owner_id == user_id
    ).all()
    
    # Log admin action
    await log_admin_action(
        db=db,
        admin_id=current_user.user_id,
        action="VIEW",
        resource_type="USER",
        resource_id=str(user_id),
        request=request
    )
    
    user_dict = user.to_dict()
    user_dict.update({
        "profile": profile.to_dict() if profile else None,
        "statistics": {
            "total_appointments": appointments,
            "owned_salons": [salon.to_dict() for salon in salons]
        }
    })
    
    return success_response(
        data=user_dict,
        message="User details retrieved successfully"
    )

@router.patch("/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "superuser"])),
    request: Request = None
):
    """
    Update user status (ACTIVE, SUSPENDED, DELETED) - required by technical specs
    """
    if status.upper() not in ["ACTIVE", "SUSPENDED", "DELETED"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    # Update user's profile status
    profile = db.query(models.Profile).join(
        models.User, models.User.keycloak_id == models.Profile.keycloak_id
    ).filter(models.User.user_id == user_id).first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    old_status = profile.status
    profile.status = status.upper()
    
    db.commit()
    db.refresh(profile)
    
    # Log admin action
    await log_admin_action(
        db=db,
        admin_id=current_user.user_id,
        action="UPDATE",
        resource_type="USER",
        resource_id=str(user_id),
        details={
            "field": "status",
            "old_value": old_status,
            "new_value": status.upper()
        },
        request=request
    )
    
    return success_response(
        data={"user_id": user_id, "new_status": status.upper()},
        message=f"User status updated to {status.upper()}"
    )

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["superuser"])),
    request: Request = None
):
    """
    Delete user (superuser only) - required by technical specs
    """
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    profile = db.query(models.Profile).filter(
        models.Profile.keycloak_id == user.keycloak_id
    ).first()
    
    # Store user data for logging before deletion
    user_data = {
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "profile_type": profile.userType if profile else None
    }
    
    # Delete profile first (due to foreign key constraint)
    if profile:
        db.delete(profile)
    
    # Delete user
    db.delete(user)
    db.commit()
    
    # Log admin action
    await log_admin_action(
        db=db,
        admin_id=current_user.user_id,
        action="DELETE",
        resource_type="USER",
        resource_id=str(user_id),
        details={"deleted_user": user_data},
        request=request
    )
    
    return success_response(
        data={"deleted_user_id": user_id},
        message="User deleted successfully"
    )

@router.get("/salons")
async def get_all_salons(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "superuser"])),
    request: Request = None
):
    """
    Get all salons with filtering - required by technical specs
    """
    query = db.query(models.Salon).join(
        models.User, models.Salon.owner_id == models.User.user_id
    ).add_columns(
        models.User.username.label("owner_username"),
        models.User.email.label("owner_email")
    )
    
    # Apply filters
    if status:
        query = query.filter(models.Salon.status == status.upper())
        
    if city:
        query = query.filter(models.Salon.city.ilike(f"%{city}%"))
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    salons = query.order_by(models.Salon.created_at.desc()).offset(skip).limit(limit).all()
    
    # Format results
    result = []
    for salon, owner_username, owner_email in salons:
        salon_dict = salon.to_dict()
        salon_dict.update({
            "owner_info": {
                "username": owner_username,
                "email": owner_email
            }
        })
        result.append(salon_dict)
    
    # Log admin action
    await log_admin_action(
        db=db,
        admin_id=current_user.user_id,
        action="VIEW",
        resource_type="SALONS",
        details={"filters": {"status": status, "city": city}},
        request=request
    )
    
    return success_response(
        data={
            "salons": result,
            "total": total,
            "skip": skip,
            "limit": limit
        },
        message="Salons retrieved successfully"
    )

@router.patch("/salons/{salon_id}/status")
async def update_salon_status(
    salon_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "superuser"])),
    request: Request = None
):
    """
    Update salon status - required by technical specs
    """
    if status.upper() not in ["ACTIVE", "INACTIVE"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    salon = db.query(models.Salon).filter(models.Salon.salon_id == salon_id).first()
    if not salon:
        raise HTTPException(status_code=404, detail="Salon not found")
    
    old_status = salon.status
    salon.status = status.upper()
    
    db.commit()
    db.refresh(salon)
    
    # Log admin action
    await log_admin_action(
        db=db,
        admin_id=current_user.user_id,
        action="UPDATE",
        resource_type="SALON",
        resource_id=str(salon_id),
        details={
            "field": "status",
            "old_value": old_status,
            "new_value": status.upper()
        },
        request=request
    )
    
    return success_response(
        data={"salon_id": salon_id, "new_status": status.upper()},
        message=f"Salon status updated to {status.upper()}"
    )

@router.get("/appointments")
async def get_all_appointments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[str] = Query(None),
    salon_id: Optional[int] = Query(None),
    client_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "superuser"])),
    request: Request = None
):
    """
    Get all appointments with filtering - required by technical specs
    """
    query = db.query(models.Appointment).join(
        models.User, models.Appointment.client_id == models.User.user_id
    ).join(
        models.Service, models.Appointment.service_id == models.Service.service_id
    ).join(
        models.Salon, models.Service.salon_id == models.Salon.salon_id
    ).add_columns(
        models.User.first_name.label("client_first_name"),
        models.User.last_name.label("client_last_name"),
        models.Service.name.label("service_name"),
        models.Salon.name.label("salon_name")
    )
    
    # Apply filters
    if status:
        query = query.filter(models.Appointment.status == status.lower())
        
    if salon_id:
        query = query.filter(models.Salon.salon_id == salon_id)
        
    if client_id:
        query = query.filter(models.Appointment.client_id == client_id)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    appointments = query.order_by(models.Appointment.appointment_time.desc()).offset(skip).limit(limit).all()
    
    # Format results
    result = []
    for appointment, client_first, client_last, service_name, salon_name in appointments:
        appointment_dict = {
            "appointment_id": appointment.appointment_id,
            "appointment_time": appointment.appointment_time,
            "duration": appointment.duration,
            "status": appointment.status,
            "notes": appointment.notes,
            "client_info": {
                "id": appointment.client_id,
                "name": f"{client_first} {client_last}"
            },
            "service_info": {
                "id": appointment.service_id,
                "name": service_name
            },
            "salon_info": {
                "name": salon_name
            },
            "created_at": appointment.created_at
        }
        result.append(appointment_dict)
    
    # Log admin action
    await log_admin_action(
        db=db,
        admin_id=current_user.user_id,
        action="VIEW",
        resource_type="APPOINTMENTS",
        details={"filters": {"status": status, "salon_id": salon_id, "client_id": client_id}},
        request=request
    )
    
    return success_response(
        data={
            "appointments": result,
            "total": total,
            "skip": skip,
            "limit": limit
        },
        message="Appointments retrieved successfully"
    )

@router.patch("/appointments/{appointment_id}/status")
async def update_appointment_status(
    appointment_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "superuser"])),
    request: Request = None
):
    """
    Update appointment status - required by technical specs
    """
    valid_statuses = ["pending", "confirmed", "completed", "cancelled"]
    if status.lower() not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    appointment = db.query(models.Appointment).filter(
        models.Appointment.appointment_id == appointment_id
    ).first()
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    old_status = appointment.status
    appointment.status = status.lower()
    
    db.commit()
    db.refresh(appointment)
    
    # Log admin action
    await log_admin_action(
        db=db,
        admin_id=current_user.user_id,
        action="UPDATE",
        resource_type="APPOINTMENT",
        resource_id=str(appointment_id),
        details={
            "field": "status",
            "old_value": old_status,
            "new_value": status.lower()
        },
        request=request
    )
    
    return success_response(
        data={"appointment_id": appointment_id, "new_status": status.lower()},
        message=f"Appointment status updated to {status.lower()}"
    )
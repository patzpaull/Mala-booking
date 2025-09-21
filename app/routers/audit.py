from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from sqlalchemy.sql import func
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from ..utils.responses import success_response
from ..dependencies import get_current_user, require_roles

router = APIRouter(prefix="/audit", tags=["audit"])

async def log_admin_action(
    db: Session,
    admin_id: int,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
    request: Optional[Request] = None
):
    """
    Helper function to log admin actions for audit trail
    """
    ip_address = None
    user_agent = None
    
    if request:
        # Get client IP (consider proxy headers)
        ip_address = request.client.host
        if "x-forwarded-for" in request.headers:
            ip_address = request.headers["x-forwarded-for"].split(",")[0].strip()
        elif "x-real-ip" in request.headers:
            ip_address = request.headers["x-real-ip"]
            
        user_agent = request.headers.get("user-agent")
    
    audit_log = models.AuditLog(
        admin_id=admin_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    db.add(audit_log)
    db.commit()
    return audit_log

@router.get("/logs")
async def get_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    admin_id: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "superuser"]))
):
    """
    Get audit logs with filtering and pagination - required by technical specs
    """
    query = db.query(models.AuditLog).join(
        models.User, models.AuditLog.admin_id == models.User.user_id
    ).add_columns(
        models.User.username,
        models.User.email,
        models.User.first_name,
        models.User.last_name
    )
    
    # Apply filters
    if action:
        query = query.filter(models.AuditLog.action == action.upper())
    
    if resource_type:
        query = query.filter(models.AuditLog.resource_type == resource_type.upper())
        
    if admin_id:
        query = query.filter(models.AuditLog.admin_id == admin_id)
    
    if start_date:
        query = query.filter(models.AuditLog.created_at >= start_date)
        
    if end_date:
        query = query.filter(models.AuditLog.created_at <= end_date)
    
    # Get total count for pagination
    total = query.count()
    
    # Apply pagination and ordering
    logs = query.order_by(models.AuditLog.created_at.desc()).offset(skip).limit(limit).all()
    
    # Format results
    result = []
    for log, username, email, first_name, last_name in logs:
        log_dict = log.to_dict()
        log_dict["admin_info"] = {
            "username": username,
            "email": email,
            "first_name": first_name,
            "last_name": last_name
        }
        result.append(log_dict)
    
    return success_response(
        data={
            "logs": result,
            "total": total,
            "skip": skip,
            "limit": limit
        },
        message="Audit logs retrieved successfully"
    )

@router.get("/summary")
async def get_audit_summary(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "superuser"]))
):
    """
    Get audit summary statistics
    """
    start_date = datetime.now() - timedelta(days=days)
    
    # Actions summary
    action_summary = db.query(
        models.AuditLog.action,
        func.count(models.AuditLog.id).label('count')
    ).filter(
        models.AuditLog.created_at >= start_date
    ).group_by(models.AuditLog.action).all()
    
    # Resource type summary
    resource_summary = db.query(
        models.AuditLog.resource_type,
        func.count(models.AuditLog.id).label('count')
    ).filter(
        models.AuditLog.created_at >= start_date
    ).group_by(models.AuditLog.resource_type).all()
    
    # Most active admins
    admin_activity = db.query(
        models.AuditLog.admin_id,
        models.User.username,
        models.User.first_name,
        models.User.last_name,
        func.count(models.AuditLog.id).label('activity_count')
    ).join(
        models.User, models.AuditLog.admin_id == models.User.user_id
    ).filter(
        models.AuditLog.created_at >= start_date
    ).group_by(
        models.AuditLog.admin_id, models.User.username, models.User.first_name, models.User.last_name
    ).order_by(
        func.count(models.AuditLog.id).desc()
    ).limit(10).all()
    
    # Daily activity trend
    daily_activity = db.query(
        func.date(models.AuditLog.created_at).label('date'),
        func.count(models.AuditLog.id).label('count')
    ).filter(
        models.AuditLog.created_at >= start_date
    ).group_by(
        func.date(models.AuditLog.created_at)
    ).order_by(
        func.date(models.AuditLog.created_at)
    ).all()
    
    return success_response(
        data={
            "period_days": days,
            "actions": [{"action": action, "count": count} for action, count in action_summary],
            "resources": [{"resource_type": resource_type, "count": count} for resource_type, count in resource_summary],
            "top_admins": [
                {
                    "admin_id": admin_id,
                    "username": username,
                    "full_name": f"{first_name} {last_name}",
                    "activity_count": count
                }
                for admin_id, username, first_name, last_name, count in admin_activity
            ],
            "daily_activity": [
                {"date": date.isoformat() if date else None, "count": count}
                for date, count in daily_activity
            ]
        },
        message="Audit summary retrieved successfully"
    )

@router.get("/actions")
async def get_available_actions(
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "superuser"]))
):
    """
    Get list of available audit actions for filtering
    """
    actions = db.query(models.AuditLog.action).distinct().all()
    resource_types = db.query(models.AuditLog.resource_type).distinct().all()
    
    return success_response(
        data={
            "actions": [action[0] for action in actions if action[0]],
            "resource_types": [resource_type[0] for resource_type in resource_types if resource_type[0]]
        },
        message="Available audit filters retrieved successfully"
    )
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from sqlalchemy.sql import func, extract
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from ..utils.responses import success_response
from ..dependencies import get_current_user, require_roles

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/general", response_model=dict)
async def get_general_analytics(db: Session = Depends(get_db)):
    """
    Retrieve general analytics data.
    """
    total_orders = db.query(models.Appointment).count()
    total_sales = db.query(func.sum(models.Payment.amount)).scalar() or 0
    total_revenue = float(total_sales) * 0.8  # Example: 80% of sales is revenue
    total_profit = float(total_sales) * 0.2  # Example: 20% of sales is profit

    return {
        "total_orders": total_orders,
        "total_sales": float(total_sales),
        "total_revenue": total_revenue,
        "total_profit": total_profit
    }

@router.get("/unique-visitors", response_model=dict)
async def get_unique_visitors(db: Session = Depends(get_db)):
    """
    Retrieve unique visitor data for the chart.
    """
    # Example data
    unique_visitors = {
        "series": [45, 52, 38, 24, 33, 26, 21],
        "categories": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    }
    return unique_visitors

@router.get("/customers", response_model=dict)
async def get_customer_analytics(db: Session = Depends(get_db)):
    """
    Retrieve customer analytics data for the chart.
    """
    total_customers = db.query(models.User).filter(models.User.role == "customer").count()
    new_customers = int(total_customers * 0.8)  # Example: 80% are new
    returning_customers = int(total_customers * 0.2)  # Example: 20% are returning

    return {
        "total_customers": total_customers,
        "new_customers": new_customers,
        "returning_customers": returning_customers
    }

@router.get("/campaign-monitor", response_model=list)
async def get_campaign_monitor_data(db: Session = Depends(get_db)):
    """
    Retrieve campaign monitor data for the table.
    """
    # Example data
    campaigns = [
        {"date": "08-11-2016", "click": 786, "cost": 485, "ctr": "45.3%", "arpu": "6.7%", "ecpi": "8.56", "roi": "10:55", "revenue": "33.8%"},
        {"date": "15-10-2016", "click": 786, "cost": 523, "ctr": "78.3%", "arpu": "6.6%", "ecpi": "7.56", "roi": "4:30", "revenue": "76.8%"},
        {"date": "08-08-2017", "click": 624, "cost": 436, "ctr": "78.3%", "arpu": "6.4%", "ecpi": "9.45", "roi": "9:05", "revenue": "8.63%"},
        {"date": "11-12-2017", "click": 423, "cost": 123, "ctr": "78.6%", "arpu": "45.6%", "ecpi": "6.85", "roi": "7:45", "revenue": "33.8%"},
    ]
    return campaigns

@router.get("/appointments-by-status")
async def get_appointments_by_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get appointments grouped by status - required by technical specs
    """
    # Query appointments by status
    status_counts = db.query(
        models.Appointment.status,
        func.count(models.Appointment.appointment_id).label('count')
    ).group_by(models.Appointment.status).all()
    
    result = {status: count for status, count in status_counts}
    
    return success_response(
        data=result,
        message="Appointments by status retrieved successfully"
    )

@router.get("/popular-services")
async def get_popular_services(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get most popular services based on appointment count - required by technical specs
    """
    popular_services = db.query(
        models.Service.name,
        models.Service.service_id,
        func.count(models.Appointment.appointment_id).label('booking_count')
    ).join(
        models.Appointment, models.Service.service_id == models.Appointment.service_id
    ).group_by(
        models.Service.service_id, models.Service.name
    ).order_by(
        func.count(models.Appointment.appointment_id).desc()
    ).limit(limit).all()
    
    result = [
        {
            "service_id": service_id,
            "name": name,
            "booking_count": count
        }
        for name, service_id, count in popular_services
    ]
    
    return success_response(
        data=result,
        message="Popular services retrieved successfully"
    )

@router.get("/messages-per-appointment")
async def get_messages_per_appointment(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get message count per appointment - required by technical specs
    """
    message_counts = db.query(
        models.Appointment.appointment_id,
        func.count(models.Message.id).label('message_count')
    ).join(
        models.Message, models.Appointment.appointment_id == models.Message.appointment_id
    ).group_by(
        models.Appointment.appointment_id
    ).all()
    
    result = [
        {
            "appointment_id": appointment_id,
            "message_count": count
        }
        for appointment_id, count in message_counts
    ]
    
    return success_response(
        data=result,
        message="Message counts per appointment retrieved successfully"
    )

@router.get("/revenue-analytics")
async def get_revenue_analytics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get comprehensive revenue analytics - required by technical specs
    """
    # Total revenue from completed payments
    total_revenue = db.query(
        func.sum(models.Payment.amount)
    ).filter(
        models.Payment.payment_status == 'completed'
    ).scalar() or 0
    
    # Revenue by payment method
    revenue_by_method = db.query(
        models.Payment.payment_method,
        func.sum(models.Payment.amount).label('revenue')
    ).filter(
        models.Payment.payment_status == 'completed'
    ).group_by(
        models.Payment.payment_method
    ).all()
    
    # Monthly revenue (last 12 months)
    monthly_revenue = db.query(
        func.extract('month', models.Payment.created_at).label('month'),
        func.extract('year', models.Payment.created_at).label('year'),
        func.sum(models.Payment.amount).label('revenue')
    ).filter(
        models.Payment.payment_status == 'completed'
    ).group_by(
        func.extract('month', models.Payment.created_at),
        func.extract('year', models.Payment.created_at)
    ).order_by(
        func.extract('year', models.Payment.created_at),
        func.extract('month', models.Payment.created_at)
    ).all()
    
    result = {
        "total_revenue": float(total_revenue),
        "revenue_by_method": [
            {"method": method, "revenue": float(revenue)}
            for method, revenue in revenue_by_method
        ],
        "monthly_revenue": [
            {"month": int(month), "year": int(year), "revenue": float(revenue)}
            for month, year, revenue in monthly_revenue
        ]
    }
    
    return success_response(
        data=result,
        message="Revenue analytics retrieved successfully"
    )

@router.get("/dashboard-summary")
async def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "superuser"]))
):
    """
    Get comprehensive dashboard summary for admin portal - covers all KPIs mentioned in technical specs
    """
    # User counts by type
    total_customers = db.query(models.Profile).filter(
        models.Profile.userType == "CUSTOMER"
    ).count()
    
    total_vendors = db.query(models.Profile).filter(
        models.Profile.userType == "VENDOR"
    ).count()
    
    total_freelancers = db.query(models.Profile).filter(
        models.Profile.userType == "FREELANCE"
    ).count()
    
    total_admins = db.query(models.Profile).filter(
        models.Profile.userType == "ADMIN"
    ).count()
    
    total_users = total_customers + total_vendors + total_freelancers + total_admins
    
    # Salon counts
    total_salons = db.query(models.Salon).count()
    active_salons = db.query(models.Salon).filter(
        models.Salon.status == 'ACTIVE'
    ).count()
    inactive_salons = total_salons - active_salons
    
    # Service and appointment counts
    total_services = db.query(models.Service).count()
    total_appointments = db.query(models.Appointment).count()
    
    # Appointment status breakdown
    pending_appointments = db.query(models.Appointment).filter(
        models.Appointment.status == 'pending'
    ).count()
    confirmed_appointments = db.query(models.Appointment).filter(
        models.Appointment.status == 'confirmed'
    ).count()
    completed_appointments = db.query(models.Appointment).filter(
        models.Appointment.status == 'completed'
    ).count()
    cancelled_appointments = db.query(models.Appointment).filter(
        models.Appointment.status == 'cancelled'
    ).count()
    
    # Revenue metrics
    total_revenue = db.query(
        func.sum(models.Payment.amount)
    ).filter(
        models.Payment.payment_status == 'completed'
    ).scalar() or 0
    
    # Message counts
    total_messages = db.query(models.Message).count()
    
    # Growth metrics (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    new_users_this_month = db.query(models.Profile).filter(
        models.Profile.created_at >= thirty_days_ago
    ).count()
    
    new_appointments_this_month = db.query(models.Appointment).filter(
        models.Appointment.created_at >= thirty_days_ago
    ).count()
    
    return success_response(
        data={
            "users": {
                "total": total_users,
                "customers": total_customers,
                "vendors": total_vendors,
                "freelancers": total_freelancers,
                "admins": total_admins,
                "new_this_month": new_users_this_month
            },
            "salons": {
                "total": total_salons,
                "active": active_salons,
                "inactive": inactive_salons
            },
            "services": {
                "total": total_services
            },
            "appointments": {
                "total": total_appointments,
                "pending": pending_appointments,
                "confirmed": confirmed_appointments,
                "completed": completed_appointments,
                "cancelled": cancelled_appointments,
                "new_this_month": new_appointments_this_month
            },
            "revenue": {
                "total": float(total_revenue)
            },
            "messages": {
                "total": total_messages
            }
        },
        message="Dashboard summary retrieved successfully"
    )

@router.get("/users-growth")
async def get_users_growth(
    period: str = Query("monthly", regex="^(daily|weekly|monthly)$"),
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "superuser"]))
):
    """
    Get user growth data over time segmented by role - required by technical specs
    """
    # Calculate date grouping based on period
    if period == "daily":
        date_trunc = func.date_trunc('day', models.Profile.created_at)
        days_back = 30
    elif period == "weekly":
        date_trunc = func.date_trunc('week', models.Profile.created_at)
        days_back = 84  # 12 weeks
    else:  # monthly
        date_trunc = func.date_trunc('month', models.Profile.created_at)
        days_back = 365  # 12 months
    
    start_date = datetime.now() - timedelta(days=days_back)
    
    # Get user growth by role
    growth_data = db.query(
        date_trunc.label('period'),
        models.Profile.userType,
        func.count(models.Profile.profile_id).label('count')
    ).filter(
        models.Profile.created_at >= start_date
    ).group_by(
        date_trunc, models.Profile.userType
    ).order_by(
        date_trunc
    ).all()
    
    # Format data for frontend
    result = {}
    for period_date, user_type, count in growth_data:
        period_str = period_date.isoformat() if period_date else "unknown"
        if period_str not in result:
            result[period_str] = {"period": period_str, "customers": 0, "vendors": 0, "freelancers": 0, "admins": 0}
        
        if user_type == "CUSTOMER":
            result[period_str]["customers"] = count
        elif user_type == "VENDOR":
            result[period_str]["vendors"] = count
        elif user_type == "FREELANCE":
            result[period_str]["freelancers"] = count
        elif user_type == "ADMIN":
            result[period_str]["admins"] = count
    
    return success_response(
        data=list(result.values()),
        message=f"User growth data ({period}) retrieved successfully"
    )

@router.get("/top-salons")
async def get_top_salons(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "superuser"]))
):
    """
    Get most booked salons - required by technical specs
    """
    top_salons = db.query(
        models.Salon.salon_id,
        models.Salon.name,
        models.Salon.city,
        func.count(models.Appointment.appointment_id).label('booking_count')
    ).join(
        models.Service, models.Salon.salon_id == models.Service.salon_id
    ).join(
        models.Appointment, models.Service.service_id == models.Appointment.service_id
    ).group_by(
        models.Salon.salon_id, models.Salon.name, models.Salon.city
    ).order_by(
        func.count(models.Appointment.appointment_id).desc()
    ).limit(limit).all()
    
    result = [
        {
            "salon_id": salon_id,
            "name": name,
            "city": city,
            "booking_count": booking_count
        }
        for salon_id, name, city, booking_count in top_salons
    ]
    
    return success_response(
        data=result,
        message="Top salons retrieved successfully"
    )

@router.get("/appointments-trend")
async def get_appointments_trend(
    period: str = Query("monthly", regex="^(daily|weekly|monthly)$"),
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "superuser"]))
):
    """
    Get booking trends by day/week/month - required by technical specs
    """
    # Calculate date grouping and period
    if period == "daily":
        date_trunc = func.date_trunc('day', models.Appointment.created_at)
        days_back = 30
    elif period == "weekly":
        date_trunc = func.date_trunc('week', models.Appointment.created_at)
        days_back = 84  # 12 weeks
    else:  # monthly
        date_trunc = func.date_trunc('month', models.Appointment.created_at)
        days_back = 365  # 12 months
    
    start_date = datetime.now() - timedelta(days=days_back)
    
    trend_data = db.query(
        date_trunc.label('period'),
        models.Appointment.status,
        func.count(models.Appointment.appointment_id).label('count')
    ).filter(
        models.Appointment.created_at >= start_date
    ).group_by(
        date_trunc, models.Appointment.status
    ).order_by(
        date_trunc
    ).all()
    
    # Format data for frontend
    result = {}
    for period_date, status, count in trend_data:
        period_str = period_date.isoformat() if period_date else "unknown"
        if period_str not in result:
            result[period_str] = {
                "period": period_str,
                "pending": 0,
                "confirmed": 0,
                "completed": 0,
                "cancelled": 0,
                "total": 0
            }
        
        result[period_str][status] = count
        result[period_str]["total"] += count
    
    return success_response(
        data=list(result.values()),
        message=f"Appointment trends ({period}) retrieved successfully"
    )

@router.get("/salons-location")
async def get_salons_by_location(
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "superuser"]))
):
    """
    Get salon distribution by location - required by technical specs
    """
    location_data = db.query(
        models.Salon.city,
        models.Salon.state,
        models.Salon.country,
        func.count(models.Salon.salon_id).label('salon_count'),
        func.avg(models.Salon.latitude).label('avg_latitude'),
        func.avg(models.Salon.longitude).label('avg_longitude')
    ).group_by(
        models.Salon.city, models.Salon.state, models.Salon.country
    ).having(
        models.Salon.city.isnot(None)
    ).order_by(
        func.count(models.Salon.salon_id).desc()
    ).all()
    
    result = [
        {
            "city": city,
            "state": state,
            "country": country,
            "salon_count": salon_count,
            "coordinates": {
                "latitude": float(avg_lat) if avg_lat else None,
                "longitude": float(avg_lng) if avg_lng else None
            }
        }
        for city, state, country, salon_count, avg_lat, avg_lng in location_data
    ]
    
    return success_response(
        data=result,
        message="Salon location distribution retrieved successfully"
    )
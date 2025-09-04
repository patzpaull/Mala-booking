from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from sqlalchemy.sql import func
from typing import Dict, List
from ..utils.responses import success_response
from ..dependencies import get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/general", response_model=dict)
async def get_general_analytics(db: Session = Depends(get_db)):
    """
    Retrieve general analytics data.
    """
    total_orders = db.query(models.Appointment).count()
    total_sales = db.query(func.sum(models.Payment.amount)).scalar() or 0
    total_revenue = total_sales * 0.8  # Example: 80% of sales is revenue
    total_profit = total_sales * 0.2  # Example: 20% of sales is profit

    return {
        "total_orders": total_orders,
        "total_sales": total_sales,
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
    new_customers = total_customers * 0.8  # Example: 80% are new
    returning_customers = total_customers * 0.2  # Example: 20% are returning

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
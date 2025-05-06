from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from sqlalchemy.sql import func

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
# app/scheduler.py

import asyncio
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from sqlalchemy import and_
from . import models
from .database import get_db
from .utils.cache import invalidate_profiles_cache

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def cleanup_expired_sessions():
    """
    Clean up expired user sessions and tokens
    Run every 6 hours
    """
    try:
        logger.info("Running cleanup of expired sessions")
        # Add logic to clean up expired sessions from your session store
        # This could be Redis, database, or any other session storage
        logger.info("Expired sessions cleanup completed")
    except Exception as e:
        logger.error(f"Error during session cleanup: {e}")


async def send_appointment_reminders():
    """
    Send reminders for upcoming appointments
    Run every hour
    """
    try:
        logger.info("Checking for appointments needing reminders")
        db = next(get_db())

        # Get appointments that are 24 hours away and haven't been reminded
        tomorrow = datetime.now() + timedelta(hours=24)
        upcoming_appointments = db.query(models.Appointment).filter(
            and_(
                models.Appointment.appointment_time >= datetime.now(),
                models.Appointment.appointment_time <= tomorrow,
                models.Appointment.status == "confirmed"
            )
        ).all()

        for appointment in upcoming_appointments:
            # Here you would integrate with email/SMS service
            logger.info(f"Reminder needed for appointment {appointment.appointment_id}")
            # TODO: Send email/SMS reminder

        db.close()
        logger.info(f"Processed {len(upcoming_appointments)} appointment reminders")
    except Exception as e:
        logger.error(f"Error sending appointment reminders: {e}")


async def update_expired_appointments():
    """
    Update status of past appointments that are still pending/confirmed
    Run every hour
    """
    try:
        logger.info("Updating expired appointments")
        db = next(get_db())

        # Find appointments that are past their time and still not completed/cancelled
        expired_appointments = db.query(models.Appointment).filter(
            and_(
                models.Appointment.appointment_time < datetime.now(),
                models.Appointment.status.in_(["pending", "confirmed"])
            )
        ).all()

        for appointment in expired_appointments:
            appointment.status = "completed"
            logger.info(f"Auto-completed appointment {appointment.appointment_id}")

        if expired_appointments:
            db.commit()

        db.close()
        logger.info(f"Updated {len(expired_appointments)} expired appointments")
    except Exception as e:
        logger.error(f"Error updating expired appointments: {e}")


async def cleanup_inactive_profiles():
    """
    Archive or flag profiles that haven't been active for a long time
    Run daily at 2 AM
    """
    try:
        logger.info("Checking for inactive profiles")
        db = next(get_db())

        # Find profiles that haven't been updated in 180 days
        six_months_ago = (datetime.now() - timedelta(days=180)).date()
        inactive_profiles = db.query(models.Profile).filter(
            and_(
                models.Profile.updated_at < six_months_ago,
                models.Profile.status == "ACTIVE"
            )
        ).all()

        for profile in inactive_profiles:
            # Flag as inactive but don't delete
            profile.status = "INACTIVE"
            logger.info(f"Flagging inactive profile {profile.keycloak_id}")
            # Could send reactivation email here

        if inactive_profiles:
            db.commit()

        db.close()
        logger.info(f"Processed {len(inactive_profiles)} inactive profiles")
    except Exception as e:
        logger.error(f"Error cleaning up inactive profiles: {e}")


async def cache_refresh():
    """
    Refresh cached data periodically
    Run every 30 minutes
    """
    try:
        logger.info("Refreshing cache")
        await invalidate_profiles_cache()
        # Add other cache refresh logic here
        logger.info("Cache refresh completed")
    except Exception as e:
        logger.error(f"Error refreshing cache: {e}")


async def generate_analytics_reports():
    """
    Generate and cache analytics data for admin dashboard
    Run daily at 1 AM
    """
    try:
        logger.info("Generating analytics reports")
        db = next(get_db())

        # Pre-calculate analytics data and store in cache
        total_users = db.query(models.User).count()
        total_appointments_today = db.query(models.Appointment).filter(
            models.Appointment.created_at >= datetime.now().date()
        ).count()

        analytics_data = {
            "total_users": total_users,
            "appointments_today": total_appointments_today,
            "generated_at": datetime.now().isoformat()
        }

        # Store in cache for quick admin dashboard access
        logger.info(f"Analytics report generated: {analytics_data}")

        db.close()
        logger.info("Analytics report generation completed")
    except Exception as e:
        logger.error(f"Error generating analytics reports: {e}")


async def cleanup_old_audit_logs():
    """
    Clean up audit logs older than 1 year
    Run monthly on the 1st at 3 AM
    """
    try:
        logger.info("Cleaning up old audit logs")
        db = next(get_db())

        one_year_ago = datetime.now() - timedelta(days=365)
        old_logs = db.query(models.AuditLog).filter(
            models.AuditLog.created_at < one_year_ago
        ).delete()

        db.commit()
        db.close()
        logger.info(f"Deleted {old_logs} old audit log entries")
    except Exception as e:
        logger.error(f"Error cleaning up audit logs: {e}")


def start_scheduler():
    """
    Initialize and start the scheduler with all jobs
    """
    try:
        # Cleanup expired sessions every 6 hours
        scheduler.add_job(
            cleanup_expired_sessions,
            CronTrigger(hour="*/6"),
            id="cleanup_expired_sessions",
            replace_existing=True
        )

        # Send appointment reminders every hour
        scheduler.add_job(
            send_appointment_reminders,
            CronTrigger(minute=0),
            id="send_appointment_reminders",
            replace_existing=True
        )

        # Update expired appointments every hour
        scheduler.add_job(
            update_expired_appointments,
            CronTrigger(minute=15),
            id="update_expired_appointments",
            replace_existing=True
        )

        # Cleanup inactive profiles daily at 2 AM
        scheduler.add_job(
            cleanup_inactive_profiles,
            CronTrigger(hour=2, minute=0),
            id="cleanup_inactive_profiles",
            replace_existing=True
        )

        # Refresh cache every 30 minutes
        scheduler.add_job(
            cache_refresh,
            CronTrigger(minute="*/30"),
            id="cache_refresh",
            replace_existing=True
        )

        # Generate analytics reports daily at 1 AM
        scheduler.add_job(
            generate_analytics_reports,
            CronTrigger(hour=1, minute=0),
            id="generate_analytics_reports",
            replace_existing=True
        )

        # Cleanup old audit logs monthly on the 1st at 3 AM
        scheduler.add_job(
            cleanup_old_audit_logs,
            CronTrigger(day=1, hour=3, minute=0),
            id="cleanup_old_audit_logs",
            replace_existing=True
        )

        scheduler.start()
        logger.info("Scheduler started successfully with all jobs")
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")


def stop_scheduler():
    """
    Stop the scheduler gracefully
    """
    try:
        scheduler.shutdown()
        logger.info("Scheduler stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")

from aiocache import cached, caches
from ..models import Service, Appointment, Message, Salon, User, Profile, Staff, Payment


@cached(ttl=60, key="services:*")
async def get_cached_service(db_session):
    services = db_session.query(Service).all()
    return [service.to_dict() for service in services]


@cached(ttl=120, key="appointments:*")
async def get_cached_appointments(db_session):
    appointments = db_session.query(Appointment).all()
    return [appointment.to_dict() for appointment in appointments]


@cached(ttl=240, key="messages:*")
async def get_cached_messages(db_session):
    messages = db_session.query(Message).all()
    return [message.to_dict() for message in messages]


@cached(ttl=120, key="salons:*")
async def get_cached_salons(db_session):
    salons = db_session.query(Salon).all()
    return [salon.to_dict() for salon in salons]


@cached(ttl=120, key="profiles:*")
async def get_cached_profiles(db_session):
    profiles = db_session.query(Profile).all()
    return [profile.to_dict() for profile in profiles]


@cached(ttl=300, key="users:*")
async def get_cached_users(db_session):
    users = db_session.query(User).all()
    return [user.to_dict() for user in users]


@cached(ttl=120, key="staffs:*")
async def get_cached_staff(db_session):
    staffs = db_session.query(Staff).all()
    return [staff.to_dict() for staff in staffs]


@cached(ttl=120, key="payments:*")
async def get_cached_payment(db_session):
    payments = db_session.query(Payment).all()
    return [payment.to_dict() for payment in payments]


async def invalidate_cache(key_pattern: str):
    cache = caches.get("default")
    keys = await cache.keys(key_pattern)
    for key in keys:
        await cache.delete(key)

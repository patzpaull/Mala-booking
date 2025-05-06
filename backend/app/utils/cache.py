from aiocache import cached, Cache, caches
from typing import List, Optional
from sqlalchemy.orm import Session
from .. import models, schemas
import datetime
import json
from ..schemas import User as UserSchema, Payment as PaymentSchema, Appointment as AppointmentSchema, Message as MessageSchema, Salon as SalonSchema, Staff as StaffSchema, Profile as ProfileSchema, Payment as PaymentSchema, Service as ServiceSchema


now = datetime.datetime.now().isoformat()
# Configure cache with better settings
cache = Cache(Cache.MEMORY, ttl=300)  # 5 minute TTL


# Custom JSON encoder to handle date serialization
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime, datetime.time)):
            return obj.isoformat()
        return super().default(obj)


@cached(ttl=300, key="services:*")
async def get_cached_service(db_session) -> Optional[List[dict]]:
    """Get cached Services"""
    cached_services = await cache.get('services_list')
    if cached_services:
        return json.loads(cached_services)
    return None


async def cache_services_response(services: List[ServiceSchema]):
    """Cache the payments response with a 5 minute TTL"""
    serialized = [service.model_dump() for service in services]
    await cache.set('services_list', json.dumps(serialized, cls=CustomJSONEncoder))


async def invalidate_services_cache():
    """Invalidate the services cache"""
    await cache.delete('services_list')


@cached(ttl=120, key="appointments:*")
async def get_cached_appointments(db_session) -> Optional[List[dict]]:
    """ Get Cached Appointments"""
    cached_appointments = await cache.get('appointments_list')
    if cached_appointments:
        return json.loads(cached_appointments)
    return None


async def cache_appointments_response(appointments: List[AppointmentSchema]):
    """Cache the appointments response with a 5 minute TTL"""
    serialized = [appointment.model_dump() for appointment in appointments]
    await cache.set('appointments_list', json.dumps(serialized, cls=CustomJSONEncoder))


async def invalidate_appointments_cache():
    """Invalidate the appointments cache"""
    await cache.delete('appointments_list')


@cached(ttl=240, key="messages:*")
async def get_cached_messages(db_session) -> Optional[List[dict]]:
    """Get Cached Messages"""
    cached_messages = await cache.get('messages_list')
    if cached_messages:
        return json.loads(cached_messages)
    return None


async def cache_messages_response(messages: List[MessageSchema]):
    """Cache the messages response with a 5 minute TTL"""
    serialized = [message.model_dump() for message in messages]
    await cache.set('messages_list', json.dumps(now, cls=CustomJSONEncoder))


async def invalidate_messages_cache():
    """Invalidate the messages cache"""
    await cache.delete('messages_list')


@cached(ttl=120, key="salons:*")
async def get_cached_salons(db_session) -> Optional[List[dict]]:
    """Get cached Salons"""
    cached_salons = await cache.get('salons_list')
    if cached_salons:
        return json.loads(cached_salons)
    return None


async def cache_salons_response(salons: List[SalonSchema]):
    """Cache the salons response with a 5 minute TTL"""
    serialized = [salon.model_dump() for salon in salons]
    await cache.set('salons_list', json.dumps(serialized, cls=CustomJSONEncoder))


async def invalidate_salons_cache():
    """Invalidate the salons cache"""
    await cache.delete('salons_list')


@cached(ttl=120, key="profiles:*")
async def get_cached_profiles(keycloak_id: str, db: Session) -> Optional[schemas.Profile]:
    """
    Get cached Profile
    """

    db_profile = db.query(models.Profile).filter(
        models.Profile.keycloak_id == keycloak_id).first()
    if db_profile:
        profile_dict = db_profile.to_dict()
        return schemas.Profile.model_validate(profile_dict)
        # return schemas.Profile.model_validate(db_profile)
    return None


async def cache_profiles_response(profiles: List[models.Profile]):
    """
    Cache the profiles response with a 5 minute TTL
    """
    serialized = [profile.model_dump() for profile in profiles]
    await cache.set('profiles_list', json.dumps(serialized, cls=CustomJSONEncoder))


async def invalidate_profiles_cache():
    """Invalidate the profiles cache"""
    await cache.delete('profiles_list')


@cached(ttl=300, key="admin_analytics")
async def get_cached_admin_analytics() -> Optional[dict]:
    """Get cached admin analytics data"""
    cached_data = await cache.get("admin_analytics")
    if cached_data:
        return json.loads(cached_data)
    return None


async def cache_admin_analytics_response(analytics_data: dict):
    """Cache admin analytics data with a 5-minute TTL"""
    await cache.set("admin_analytics", json.dumps(analytics_data, cls=CustomJSONEncoder))


@cached(ttl=300, key="customer_analytics:{keycloak_id}")
async def get_cached_customer_analytics(keycloak_id: str) -> Optional[dict]:
    """Get cached customer analytics data"""
    cached_data = await cache.get(f"customer_analytics:{keycloak_id}")
    if cached_data:
        return json.loads(cached_data)
    return None


async def cache_customer_analytics_response(keycloak_id: str, analytics_data: dict):
    """Cache customer analytics data with a 5-minute TTL"""
    await cache.set(f"customer_analytics:{keycloak_id}", json.dumps(analytics_data, cls=CustomJSONEncoder))


@cached(ttl=300, key="users:*")
async def get_cached_users(db_session) -> Optional[List[dict]]:
    """Get cached users with their roles"""
    cached_data = await cache.get('users_list')
    if cached_data:
        return json.loads(cached_data)
    return None


async def cache_users_response(users: List[UserSchema]):
    """Cache the users response with a 5 minute TTL"""
    serialized = [user.model_dump() for user in users]
    await cache.set('users_list', json.dumps(serialized, cls=CustomJSONEncoder))


async def invalidate_users_cache():
    """Invalidate the users cache"""
    await cache.delete('users_list')


@cached(ttl=120, key="staffs:*")
async def get_cached_staff(db_session) -> Optional[List[dict]]:
    """Get cached Staffs"""
    cached_staffs = await cache.get('staffs_list')
    if cached_staffs:
        return json.loads(cached_staffs)
    return None


async def cache_staffs_response(staffs: List[StaffSchema]):
    """Cache the staffs response with a 5 minute TTL"""
    serialized = [staff.model_dump() for staff in staffs]
    await cache.set('staffs_list', json.dumps(serialized, cls=CustomJSONEncoder))


async def invalidate_staffs_cache():
    """Invalidate the staffs cache"""
    await cache.delete('staffs_list')


@cached(ttl=120, key="payments:*")
async def get_cached_payment(db_session) -> Optional[List[dict]]:
    """Get cached Payments"""
    cached_payments = await cache.get("payment_list")
    if cached_payments:
        return json.loads(cached_payments)
    return None


async def cache_payments_response(payments: List[PaymentSchema]):
    """Cache the payments response with a 5 minute TTL"""
    serialized = [payment.model_dump() for payment in payments]
    await cache.set('payments_list', json.dumps(serialized, cls=CustomJSONEncoder))


async def invalidate_payments_cache():
    """Invalidate the payments cache"""
    await cache.delete('payments_list')


async def invalidate_cache(key_pattern: str):
    cache = caches.get("default")
    keys = await cache.keys(key_pattern)
    for key in keys:
        await cache.delete(key)

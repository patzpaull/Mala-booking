from pydantic import BaseModel, Field, validator
from datetime import date, time, datetime
from typing import Optional, List, Dict, Any


# Appointment Schemas
class AppointmentBase(BaseModel):
    appointment_time: date
    duration: int
    notes: Optional[str] = None
    reminder_time: Optional[time] = None
    status: Optional[str] = None

    class Config:
        from_attributes: True


class Appointment(AppointmentBase):
    appointment_id: int
    client_id: int
    service_id: int
    staff_id: Optional[int]

    class Config:
        from_attributes: True


class AppointmentCreate(BaseModel):
    appointment_time: date
    duration: int
    client_id: int
    service_id: int
    staff_id: Optional[int] = None
    notes: Optional[str] = None
    reminder_time: Optional[time] = None
    status: Optional[str] = "pending"

    class Config:
        from_attributes: True


class AppointmentUpdate(BaseModel):
    appointment_time: Optional[date] = None
    duration: Optional[int] = None
    notes: Optional[str] = None
    reminder_time: Optional[time] = None
    status: Optional[str] = None

    class Config:
        from_attributes: True


class PaginatedAppointment(BaseModel):
    total: int
    items: List[Appointment]

# User Schema


class UserBase(BaseModel):
    username: str
    email: str
    first_name: str
    last_name: str

    class Config:
        from_attributes: True


class User(BaseModel):
    user_id: int
    keycloak_id: str
    email: str
    username: str
    first_name: str
    last_name: str
    role: str

    class Config:
        from_attributes = True


class PaginatedUser(BaseModel):
    total: int
    items: List[User]


class UserCreate(UserBase):
    email: str
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    first_name: str
    last_name: str
    role: str  # e.g., "USER", "ADMIN"

    class Config:
        from_attributes: True


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None

    class Config:
        from_attributes: True


class UserInfo(BaseModel):
    user_id: int
    keycloak_id: str
    username: str
    email: str
    first_name: str
    last_name: str
    role: str


class SignupRequest(UserCreate):
    pass


class SignupResponse(BaseModel):
    user_id: int
    keycloak_id: str
    email: Optional[str]
    username: str
    first_name: str
    last_name: str
    role: str
    message: str

    class Config:
        from_attributes: True


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    id_token: str | None = None  # Make id_token optional
    token_type: str = "Bearer"
    expires_in: int = 300
    refresh_expires_in: int | None = 1800
    csrf_token: Optional[str] = None
    user_info: Optional[Dict[str, Any]] = None
    # roles: List[str] = []
    # username: str
    # keycloak_id: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class Claims(BaseModel):
    id: str = Field(..., alias="sub")  # Map 'sub' to 'id'
    email: Optional[str]
    name: Optional[str] = None
    preferred_username: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    exp: int
    iat: int
    iss: str
    # sub: str
    aud: str

    class Config:
        allow_population_by_field_name: True
        from_attributes: True

# Profile Schemas


class VendorData(BaseModel):
    businessName: Optional[str]
    businessCategory: Optional[str]
    rating: Optional[float]

    class Config:
        from_attributes: True


class PaginatedVendorData(BaseModel):
    total: int
    items: List[VendorData]


class FreelancerData(BaseModel):
    skills: Optional[List[str]]
    portfolio: Optional[str]

    class Config:
        from_attributes: True


class PaginatedFreelancerData(BaseModel):
    total: int
    items: List[FreelancerData]


# Make AdditionalData completely flexible to accept any JSON structure
# This allows both dict and flexible field structures

class AdditionalData(BaseModel):
    class Config:
        extra = "allow"
        from_attributes = True

class PaginatedAdditionalData(BaseModel):
    total: int
    items: List[AdditionalData]


class ProfileBase(BaseModel):
    user_id: Optional[int] = None
    userType: str
    firstName: str
    lastName: str
    email:  Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    status: Optional[str] = None
    additionalData: Optional[dict] = None
    # username: Optional[str] = None

    class Config:
        from_attributes: True


class Profile(BaseModel):
    user_id: int
    keycloak_id: str
    firstName: str
    lastName: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    userType: Optional[str] = None
    additionalData: Optional[dict] = None
    username: Optional[str] = None
    tokens: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes: True


class PaginatedProfile(BaseModel):
    total: int
    items: List[Profile]


class ProfileCreate(ProfileBase):
    firstName: str
    lastName: str
    # username: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    password: str
    userType: Optional[str] = None
    additionalData: Optional[dict] = None

    class Config:
        from_attributes: True


@validator('firstName', 'lastName')
def validate_name(cls, v):
    if not v.isalpha():
        raise ValueError('Name must contain only letters')
    return v


@validator('userType')
def validate_userType(cls, v):
    valid_user_types = ['CUSTOMER', 'VENDOR', 'ADMIN', 'FREELANCER']
    if v not in valid_user_types:
        raise ValueError(
            f'Invalid userType must be one of {valid_user_types} ')
    return v


class ProfileUpdate(BaseModel):
    # username: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    password: Optional[str] = None
    status: Optional[str] = None
    userType: Optional[str] = None
    additionalData: Optional[dict] = None


# Message Schema
class MessageBase(BaseModel):
    message_text: str
    # sent_time: Optional[date] = None


class Message(MessageBase):
    id: int
    sender_id: int
    receiver_id: int
    appointment_id: int
    sent_time: Optional[time] = None

    class Config:
        from_attributes: True


class MessageCreate(MessageBase):
    receiver_id: int


class MessageUpdate(BaseModel):
    message_text: Optional[str] = None

    class Config:
        from_attributes: True


# Service Schema
class ServiceBase(BaseModel):
    salon_id: int
    name: str
    description: Optional[str] = None
    duration: int
    price: float

    class Config:
        from_attributes: True


class Service(ServiceBase):
    service_id: int

    class Config:
        from_attributes: True


class ServiceCreate(ServiceBase):
    name: str
    description: Optional[str] = None
    price: float

    class Config:
        from_attributes: True


class ServiceUpdate(ServiceBase):
    name: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[int] = None
    price: Optional[float] = None
    salon_id: Optional[int] = None

    class Config:
        from_attributes: True


class PaginatedService(BaseModel):
    total: int
    items: List[Service]

# Salon Schema


class SalonBase(BaseModel):
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone_number: Optional[str] = None
    website: Optional[str] = None
    social_media_links: Optional[Dict[str, str]] = None
    status: Optional[str] = "ACTIVE"  # New field
    opening_hours: Optional[Dict[str, Dict[str, str]]] = None  # New f

    class Config:
        from_attributes: True


class Salon(SalonBase):
    salon_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes: True


class SalonCreate(SalonBase):
    name: str
    description: str
    image_url: Optional[str]
    owner_id: int
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    street: Optional[str] = None
    country: Optional[str] = None
    

    class Config:
        from_attributes: True


class SalonUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone_number: Optional[str] = None
    website: Optional[str] = None
    social_media_links: Optional[Dict[str, str]] = None
    status: Optional[str] = "ACTIVE"  # New field
    opening_hours: Optional[Dict[str, Dict[str, str]]] = None

    class Config:
        from_attributes: True


class PaginatedSalon(BaseModel):
    total: int
    items: List[Salon]

# Staff Schemas


class StaffBase(BaseModel):
    first_name: str
    last_name: str
    email: str
    role: str

    class Config:
        from_attributes: True


class Staff(StaffBase):
    staff_id: int
    # user_id: int
    salon_id: int

    class Config:
        from_attributes: True


class StaffCreate(StaffBase):
    salon_id: int
    # user_id: int

    class Config:
        from_attributes: True


class StaffUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None

    class Config:
        from_attributes: True


class PaginatedStaff(BaseModel):
    total: int
    items: List[Staff]

# Review Schemas


class ReviewBase(BaseModel):
    ratings: int
    review_text: Optional[str] = None

    class Config:
        from_attributes: True


class Review(ReviewBase):
    review_id: int
    client_id: int
    salon_id: int

    class Config:
        from_attributes: True


class ReviewCreate(ReviewBase):
    pass


class ReviewUpdate(BaseModel):
    ratings: Optional[int] = None
    review_text: Optional[str] = None

    class Config:
        from_attributes: True


class PaginatedService(BaseModel):
    total: int
    items: List[Review]

# Payment Schemas


class PaymentBase(BaseModel):
    amount: float
    payment_method: str
    payment_status: str
    transaction_id: Optional[str] = None

    class Config:
        from_attributes: True


class Payment(PaymentBase):
    payment_id: int
    appointment_id: int

    class Config:
        from_attributes: True


class PaymentCreate(PaymentBase):
    appointment_id: int


class PaymentUpdate(BaseModel):
    amount: Optional[float] = None
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    transaction_id: Optional[str] = None

    class Config:
        from_attributes: True

# Role Schema


class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None


class Role(RoleBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes: True


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

    class Config:
        from_attributes: True


# File Upload Schemas

class FileUploadResponse(BaseModel):
    message: str
    file_url: str
    uploaded_at: Optional[datetime] = None

    class Config:
        from_attributes: True


class AvatarUploadResponse(FileUploadResponse):
    user_type: str
    keycloak_id: str


class SalonImageUploadResponse(FileUploadResponse):
    salon_id: int
    image_type: str = "cover"

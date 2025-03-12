from pydantic import BaseModel, Field
from datetime import date, time
from typing import Optional, List


# Appointment Schemas
class AppointmentBase(BaseModel):
    appointment_time: date
    duration: int
    notes: Optional[str] = None
    reminder_time: Optional[time] = None
    status: Optional[str] = None


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


class AppointmentUpdate(BaseModel):
    appointment_time: Optional[date] = None
    duration: Optional[int] = None
    notes: Optional[str] = None
    reminder_time: Optional[time] = None
    status: Optional[str] = None

    class Config:
        from_attributes: True


# User Schema
class UserBase(BaseModel):
    username: str
    email: str
    first_name: str
    last_name: str


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


class UserCreate(UserBase):
    email: str
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    first_name: str
    last_name: str
    role: str  # e.g., "USER", "ADMIN"


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None

    class Config:
        from_attributes: True


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
    refresh_expires_in: int = 1800


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
    aud: str

    class Config:
        allow_population_by_filed_name = True
        from_attributes: True

# Profile Schemas


class ProfileBase(BaseModel):
    user_id: int
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    # username: Optional[str] = None

    class Config:
        from_attributes: True


class Profile(ProfileBase):
    profile_id: int
    user_id: int  # Add this field
    username: str
    bio: Optional[str] = None
    avatar_url: Optional[str] = None

    class Config:
        from_attributes: True


class ProfileCreate(ProfileBase):
    user_id: int
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    username: str  # Add the username field


class ProfileUpdate(BaseModel):
    bio: Optional[str] = None
    avatar_url: Optional[str] = None

    class Config:
        from_attributes: True


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


class Service(ServiceBase):
    service_id: int

    class Config:
        from_attributes: True


class ServiceCreate(ServiceBase):
    name: str
    description: Optional[str] = None
    price: float


class ServiceUpdate(ServiceBase):
    name: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[int] = None
    price: Optional[float] = None

    class Config:
        from_attributes: True


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


class Salon(SalonBase):
    salon_id: int

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


class SalonUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None

    class Config:
        from_attributes: True


# Staff Schemas
class StaffBase(BaseModel):
    first_name: str
    last_name: str
    email: str
    role: str


class Staff(StaffBase):
    staff_id: int
    user_id: int
    salon_id: int

    class Config:
        from_attributes: True


class StaffCreate(StaffBase):
    salon_id: int
    user_id: int


class StaffUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None

    class Config:
        from_attributes: True


# Review Schemas
class ReviewBase(BaseModel):
    ratings: int
    review_text: Optional[str] = None


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


# Payment Schemas
class PaymentBase(BaseModel):
    amount: float
    payment_method: str
    payment_status: str
    transaction_id: Optional[str] = None


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
    created_at: Optional[time] = None
    updated_at: Optional[time] = None

    class Config:
        from_attributes: True


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

    class Config:
        from_attributes: True

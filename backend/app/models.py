
from .database import Base
from sqlalchemy import Column, Integer, String, Date, Time, ForeignKey, Numeric, Text
from sqlalchemy.orm import relationship, mapped_column
from sqlalchemy.sql import func
# from datetime import datetime
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Appointment(Base):
    __tablename__ = 'appointments'

    appointment_id = mapped_column(Integer, primary_key=True, index=True)
    appointment_time = mapped_column(Date, nullable=False)
    duration = mapped_column(Integer, nullable=False)
    notes = mapped_column(Text, nullable=True)
    client_id = mapped_column(Integer, ForeignKey(
        'users.user_id'), nullable=False)
    service_id = mapped_column(Integer, ForeignKey(
        'services.service_id'), nullable=False)
    reminder_time = mapped_column(Time, nullable=True)
    staff_id = mapped_column(Integer, ForeignKey(
        'staff.staff_id'), nullable=True)
    status = mapped_column(String(20), nullable=False, default='pending')
    created_at = mapped_column(Date, default=func.now())
    updated_at = mapped_column(Date, onupdate=func.now())

    client = relationship('User', back_populates="appointments")
    service = relationship('Service', back_populates="appointments")
    staff = relationship('Staff', back_populates="appointments")
    payments = relationship('Payment', back_populates="appointment")
    messages = relationship('Message', back_populates="appointment")


class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True, index=True)
    keycloak_id = Column(String, unique=True, index=True, nullable=False)
    username = mapped_column(String(255), nullable=False, unique=True)
    email = mapped_column(String(254), nullable=False, unique=True)
    password_hash = mapped_column(String(255), nullable=False)
    first_name = mapped_column(String(255), nullable=False)
    last_name = mapped_column(String(255), nullable=False)
    role_id = mapped_column(Integer, ForeignKey('roles.id'), nullable=False)
    created_at = mapped_column(Date, default=func.now())
    updated_at = mapped_column(Date, onupdate=func.now())

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'role_id': self.role_id,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

    role = relationship('Role', back_populates="users")
    appointments = relationship('Appointment', back_populates="client")
    reviews = relationship('Review', back_populates="client")
    profile = relationship('Profile', back_populates="user", uselist=False)
    salon = relationship('Salon', back_populates="owner")
    staff_member = relationship('Staff', back_populates='user', uselist=False)
    sent_messages = relationship(
        'Message', foreign_keys='Message.sender_id', back_populates='sender', uselist=False)
    received_messages = relationship(
        'Message', foreign_keys='Message.receiver_id', back_populates='receiver', uselist=False)

    def verify_password(self, password: str):
        return pwd_context.verify(password, self.password_hash)

    def set_password(self, password: str):
        self.password_hash = pwd_context.hash(password)

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "keycloak_id": self.keycloak_id,
            "username": self.username,
            "email": self.email,
            "password_hash": self.password_hash,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "role_id": self.role_id,
        }


class Profile(Base):
    __tablename__ = 'profiles'
    profile_id = mapped_column(Integer, primary_key=True)
    bio = mapped_column(Text, nullable=True)
    avatar_url = Column(String)
    user_id = mapped_column(Integer, ForeignKey(
        'users.user_id'), nullable=False, unique=True)
    username = Column(String, nullable=False)
    created_at = mapped_column(Date)
    updated_at = mapped_column(Date)

    user = relationship('User', back_populates="profile")

    def to_dict(self):
        return {
            "profile_id": self.profile_id,
            "bio": self.bio,
            "avatar_url": self.avatar_url,
            "user_id": self.user_id,
            "username": self.username,
        }


class Message(Base):
    __tablename__ = 'messages'
    id = mapped_column(Integer, primary_key=True)
    sender_id = mapped_column(Integer, ForeignKey(
        'users.user_id'), nullable=False)
    receiver_id = mapped_column(
        Integer, ForeignKey('users.user_id'), nullable=False)
    appointment_id = mapped_column(Integer, ForeignKey(
        'appointments.appointment_id'), nullable=False)
    message_text = mapped_column(Text, nullable=False)
    sent_time = mapped_column(Date, default=func.now(), nullable=False)

    sender = relationship('User', foreign_keys=[
                          sender_id], back_populates='sent_messages')
    receiver = relationship('User', foreign_keys=[
                            receiver_id], back_populates='received_messages')
    appointment = relationship('Appointment', back_populates="messages")

    def to_dict(self):
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "appointment_id": self.appointment_id,
            "message_text": self.message_text,
            "sent_time": self.sent_time,
        }


class Service(Base):
    __tablename__ = 'services'
    service_id = mapped_column(Integer, primary_key=True)
    name = mapped_column(String(255), nullable=False)
    description = mapped_column(String(254), nullable=False, unique=True)
    duration = mapped_column(Integer, nullable=False)
    price = mapped_column(Numeric(10, 2), nullable=False)
    salon_id = mapped_column(Integer, ForeignKey(
        'salons.salon_id'), nullable=False)
    created_at = mapped_column(Date)
    updated_at = mapped_column(Date)

    appointments = relationship('Appointment', back_populates="service")
    salon = relationship('Salon', back_populates="services")

    def to_dict(self):
        return {
            "service_id": self.service_id,
            "name": self.name,
            "description": self.description,
            "duration": self.duration,
            "price": self.price,
            "salon_id": self.salon_id,
        }


class Salon(Base):
    __tablename__ = 'salons'
    salon_id = mapped_column(Integer, primary_key=True)
    name = mapped_column(String(255), nullable=False)
    description = mapped_column(Text, nullable=True)
    image_url = mapped_column(String(255), nullable=True)
    owner_id = mapped_column(Integer, ForeignKey(
        'users.user_id'), nullable=False)
    street = mapped_column(String(255), nullable=True)
    city = mapped_column(String(100), nullable=True)
    state = mapped_column(String(100), nullable=True)
    zip_code = mapped_column(String(20), nullable=True)
    country = mapped_column(String(100), nullable=True)
    created_at = mapped_column(Date)
    updated_at = mapped_column(Date)

    owner = relationship('User', back_populates="salon")
    services = relationship('Service', back_populates="salon")
    reviews = relationship('Review', back_populates="salon")
    staff_member = relationship('Staff', back_populates="salon")

    def to_dict(self):
        return {
            "salon_id": self.salon_id,
            "name": self.name,
            "description": self.description,
            "image_url": self.image_url,
            "owner_id": self.owner_id,
            "street": self.street,
            "city": self.city,
            "state": self.state,
            "zip_code": self.zip_code,
            "country": self.country,
        }


class Staff(Base):
    __tablename__ = 'staff'
    staff_id = mapped_column(Integer, primary_key=True)
    user_id = mapped_column(Integer, ForeignKey(
        'users.user_id'), nullable=False, unique=True)
    salon_id = mapped_column(Integer, ForeignKey(
        'salons.salon_id'), nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    role = mapped_column(String(50), nullable=False)
    created_at = mapped_column(Date, default=func.now())
    updated_at = mapped_column(Date, onupdate=func.now())

    user = relationship('User', back_populates='staff_member', uselist=False)
    salon = relationship('Salon', back_populates='staff_member')
    appointments = relationship('Appointment', back_populates="staff")

    def to_dict(self):
        return {
            "staff_id": self.staff_id,
            "user_id": self.user_id,
            "salon_id": self.salon_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "role": self.role,
        }


class Role(Base):
    __tablename__ = 'roles'
    id = mapped_column(Integer, primary_key=True)
    name = mapped_column(String(255), nullable=False, unique=True)
    description = mapped_column(Text, nullable=True)
    created_at = mapped_column(Date)
    updated_at = mapped_column(Date)

    users = relationship('User', back_populates="role")


class Review(Base):
    __tablename__ = 'reviews'
    review_id = mapped_column(Integer, primary_key=True)
    ratings = mapped_column(Integer, nullable=True)
    review_text = mapped_column(Text, nullable=True)
    client_id = mapped_column(Integer, ForeignKey(
        'users.user_id'), nullable=False)
    salon_id = mapped_column(Integer, ForeignKey(
        'salons.salon_id', ondelete='SET NULL'), nullable=False)
    created_at = mapped_column(Date)
    updated_at = mapped_column(Date)

    client = relationship('User', back_populates="reviews")
    salon = relationship('Salon', back_populates="reviews")

    def to_dict(self):
        return {
            "review_id": self.review_id,
            "ratings": self.ratings,
            "review_text": self.review_text,
            "client_id": self.client_id,
            "salon_id": self.salon_id,
        }


class Payment(Base):
    __tablename__ = 'payments'
    payment_id = mapped_column(Integer, primary_key=True)
    appointment_id = mapped_column(Integer, ForeignKey(
        'appointments.appointment_id'), nullable=False)
    amount = mapped_column(Numeric(10, 2), nullable=False)
    payment_method = mapped_column(String(50), nullable=False)
    payment_status = mapped_column(
        String(20), nullable=False, default='pending')
    transaction_id = mapped_column(String(100), nullable=True, unique=True)
    created_at = mapped_column(Date, default=func.now())
    updated_at = mapped_column(Date, onupdate=func.now())

    appointment = relationship('Appointment', back_populates="payments")

    def to_dict(self):
        return {
            "payment_id": self.payment_id,
            "appointment_id": self.appointment_id,
            "amount": self.amount,
            "payment_method": self.payment_method,
            "payment_status": self.payment_status,
            "transaction_id": self.transaction_id,
        }


# # Additional relationships
# Appointment.payments = relationship('Payment', back_populates="appointment")
# Salon.reviews = relationship('Review', back_populates="salon")
# User.salons = relationship('Salon', back_populates="users")

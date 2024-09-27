# backend/app/models.py
from .database import Base
from sqlalchemy import Column, Integer, String , Date, Time, ForeignKey
from sqlalchemy.orm import relationship

class Appointment(Base):
    __tablename__ = 'appointments'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    time = Column(Time, nullable=False)
    duration = Column(Integer, nullable=False)

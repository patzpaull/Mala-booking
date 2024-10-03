
from .database import Base
from sqlalchemy import Column, Integer, String , Date, Time, ForeignKey
from sqlalchemy.orm import relationship,mapped_column

class Appointment(Base):
    __tablename__ = 'appointments'

    id = mapped_column(Integer, primary_key=True, index=True)
    name = mapped_column(String, nullable=False)
    date = mapped_column(Date, nullable=False)
    notes = mapped_column(String, nullable=True)
    time = mapped_column(Time, nullable=False)
    duration = mapped_column(Integer, nullable=False)

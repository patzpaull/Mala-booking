from pydantic import BaseModel
from datetime import date, time
from typing import Optional

class AppointmentBase(BaseModel):
    name: str
    date: date
    time: time
    duration: int

class Appointment(AppointmentBase):
    id:int
    name: str
    date: date
    time: time
    duration: int

class AppointmentCreate(BaseModel):
    name: str
    date: date
    time: time
    duration: int 

class AppointmentUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[date] = None
    time: Optional[time] = None 
    duration: Optional[int] = None
    
    class Config:
        orm_mode = True

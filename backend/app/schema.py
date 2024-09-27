from pydantic import BaseModel
from datetime import date, time

class AppointmentBase(BaseModel):
    name: str
    date: date
    time: time
    duration: int

class Appointment(AppointmentBase):
    id:int

    class Config:
        orm_mode = True

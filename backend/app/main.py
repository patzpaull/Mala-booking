from fastapi import FastAPI
from .database import engine, Base
from .routers import appointments
# from .models import models 
from . import models

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(appointments.router)

@app.get("/")
async def root():
    return {"message": "Hello World"}
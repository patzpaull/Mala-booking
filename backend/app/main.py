from fastapi import FastAPI
from app.database import engine, Base
from app.routers import appointments
from app.models import models 

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(appointments.router)

@app.get("/")
async def root():
    return {"message": "Hello World"}
# backend/app/main.py

from fastapi import FastAPI, WebSocket, HTTPException, Request, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse
from app.middleware.rate_limiter import RateLimiterMiddleware
from typing import List
from dotenv import load_dotenv
import os
import logging
import secrets

from app.routers import appointments, users, messages, payments, services, staffs, salons, profiles, auth, analytics

app = FastAPI(redirect_slashes=False)

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()

# Load environment variables
load_dotenv()

# Set up session middleware
session_secret_key = os.getenv("SESSION_SECRET_KEY") or secrets.token_hex(32)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust as necessary
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_errors(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logging.error(f"Unhandled error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret_key,
    same_site="lax",
    https_only=False  # Set to True in production when using HTTPS
)

app.add_middleware(RateLimiterMiddleware, max_requests=20, window_seconds=60)


# Include routers
app.include_router(users.router)
app.include_router(salons.router)
app.include_router(auth.router)
app.include_router(services.router)
app.include_router(staffs.router)
app.include_router(profiles.router)
app.include_router(appointments.router)
app.include_router(payments.router)
app.include_router(messages.router)
app.include_router(analytics.router)

# Exception handler for HTTP exceptions


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(f"You wrote: {data}", websocket)
            await manager.broadcast(f"Client {client_id} says: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client {client_id} left the chat")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred"},
    )


@app.get("/")
async def root():
    return {"message": "Welcome to the Salon Booking System API"}

# backend/app/main.py

from fastapi import FastAPI, WebSocket, HTTPException, Request, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse
from app.middleware import RateLimiterMiddleware, CompressionMiddleware, PerformanceLoggingMiddleware, CacheControlMiddleware
from typing import List
from dotenv import load_dotenv
import os
import logging
import secrets
import uvloop
import asyncio
from contextlib import asynccontextmanager

from app.routers import appointments, users, messages, payments, services, staffs, salons, profiles, auth, analytics
from app.services.keycloak import KeycloakService
from app.monitoring import log_performance_summary
from app.utils.responses import error_response

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set event loop policy for better performance
    if hasattr(uvloop, 'install'):
        uvloop.install()
    
    # Initialize services
    keycloak_service = KeycloakService()
    
    # Start performance monitoring
    monitor_task = asyncio.create_task(log_performance_summary())
    
    yield
    
    # Cleanup on shutdown
    monitor_task.cancel()
    await KeycloakService.close_http_client()

app = FastAPI(
    title="Mala Booking System",
    description="High-performance salon booking system",
    version="2.0.0",
    redirect_slashes=False,
    lifespan=lifespan
)

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

# Add performance middleware in order (last added = first executed)
app.add_middleware(CompressionMiddleware, minimum_size=500)
app.add_middleware(PerformanceLoggingMiddleware, slow_request_threshold=2.0)
app.add_middleware(CacheControlMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust as necessary
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time"]
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

app.add_middleware(RateLimiterMiddleware, max_requests=100, window_seconds=60)  # Increased limit for better performance


# Include routers with v1 versioning
app.include_router(users.router, prefix="/v1")
app.include_router(salons.router, prefix="/v1")
app.include_router(auth.router, prefix="/v1")
app.include_router(services.router, prefix="/v1")
app.include_router(staffs.router, prefix="/v1")
app.include_router(profiles.router, prefix="/v1")
app.include_router(appointments.router, prefix="/v1")
app.include_router(payments.router, prefix="/v1")
app.include_router(messages.router, prefix="/v1")
app.include_router(analytics.router, prefix="/v1")

# Exception handler for HTTP exceptions


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return error_response(message=exc.detail, code=exc.status_code)


@app.websocket("/ws/appointments/{appointment_id}")
async def websocket_endpoint(websocket: WebSocket, appointment_id: int):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Broadcast message to all participants in this appointment
            await manager.broadcast(f"Appointment {appointment_id}: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"User left appointment {appointment_id} chat")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return error_response(
        message="Validation error", 
        code=422,
        details={"errors": exc.errors(), "body": exc.body}
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return error_response(
        message="An internal server error occurred",
        code=500
    )


@app.get("/")
async def root():
    return {"message": "Welcome to the Salon Booking System API"}

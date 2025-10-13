# backend/app/main.py

from fastapi import FastAPI, WebSocket, HTTPException, Request, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse
from app.middleware import RateLimiterMiddleware, CompressionMiddleware, PerformanceLoggingMiddleware, CacheControlMiddleware
from typing import List, Dict
import json
from dotenv import load_dotenv
import os
import logging
import secrets
import uvloop
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from app.routers import appointments, users, messages, payments, services, staffs, salons, profiles, auth, analytics, audit, admin
from app.services.keycloak import KeycloakService
from app.monitoring import log_performance_summary
from app.utils.responses import error_response
from app.utils.utils import ensure_roles_exist
from app.database import get_db
from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set event loop policy for better performance
    if hasattr(uvloop, 'install'):
        uvloop.install()

    # Initialize services
    keycloak_service = KeycloakService()

    # Initialize roles in database
    try:
        db = next(get_db())
        ensure_roles_exist(db)
        logging.info("Roles initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize roles: {e}")
    finally:
        db.close()

    # Start background scheduler for periodic tasks
    try:
        start_scheduler()
        logging.info("Background scheduler started successfully")
    except Exception as e:
        logging.error(f"Failed to start scheduler: {e}")

    # Start performance monitoring
    monitor_task = asyncio.create_task(log_performance_summary())

    yield

    # Cleanup on shutdown
    monitor_task.cancel()
    stop_scheduler()
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
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.admin_connections: List[WebSocket] = []
        self.appointment_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, connection_type: str = "general", identifier: str = None):
        await websocket.accept()

        if connection_type == "admin":
            self.admin_connections.append(websocket)
        elif connection_type == "appointment" and identifier:
            appointment_id = int(identifier)
            if appointment_id not in self.appointment_connections:
                self.appointment_connections[appointment_id] = []
            self.appointment_connections[appointment_id].append(websocket)
        else:
            if connection_type not in self.active_connections:
                self.active_connections[connection_type] = []
            self.active_connections[connection_type].append(websocket)

    def disconnect(self, websocket: WebSocket, connection_type: str = "general", identifier: str = None):
        try:
            if connection_type == "admin":
                self.admin_connections.remove(websocket)
            elif connection_type == "appointment" and identifier:
                appointment_id = int(identifier)
                if appointment_id in self.appointment_connections:
                    self.appointment_connections[appointment_id].remove(
                        websocket)
                    if not self.appointment_connections[appointment_id]:
                        del self.appointment_connections[appointment_id]
            else:
                if connection_type in self.active_connections:
                    self.active_connections[connection_type].remove(websocket)
        except ValueError:
            pass  # Connection not in list

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except:
            pass  # Connection closed

    async def broadcast(self, message: str, connection_type: str = "general"):
        connections = []

        if connection_type == "admin":
            connections = self.admin_connections
        elif connection_type in self.active_connections:
            connections = self.active_connections[connection_type]

        # Send to all connections, removing broken ones
        broken_connections = []
        for connection in connections:
            try:
                await connection.send_text(message)
            except:
                broken_connections.append(connection)

        # Clean up broken connections
        for broken_connection in broken_connections:
            self.disconnect(broken_connection, connection_type)

    async def broadcast_to_appointment(self, appointment_id: int, message: str):
        if appointment_id in self.appointment_connections:
            connections = self.appointment_connections[appointment_id].copy()
            broken_connections = []

            for connection in connections:
                try:
                    await connection.send_text(message)
                except:
                    broken_connections.append(connection)

            # Clean up broken connections
            for broken_connection in broken_connections:
                self.disconnect(broken_connection,
                                "appointment", str(appointment_id))

    async def notify_admins(self, event_type: str, data: dict):
        """Send real-time notifications to admin dashboard"""
        message = json.dumps({
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })
        await self.broadcast(message, "admin")


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
    allow_origins=[
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
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

# Increased limit for better performance
app.add_middleware(RateLimiterMiddleware, max_requests=100, window_seconds=60)


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
app.include_router(audit.router, prefix="/v1")
app.include_router(admin.router, prefix="/v1")

# Exception handler for HTTP exceptions


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return error_response(message=exc.detail, code=exc.status_code)


@app.websocket("/ws/appointments/{appointment_id}")
async def websocket_appointment_endpoint(websocket: WebSocket, appointment_id: int):
    await manager.connect(websocket, "appointment", str(appointment_id))
    try:
        while True:
            data = await websocket.receive_text()
            # Broadcast message to all participants in this appointment
            await manager.broadcast_to_appointment(appointment_id, f"Appointment {appointment_id}: {data}")
            # Also notify admins of new message activity
            await manager.notify_admins("new_message", {
                "appointment_id": appointment_id,
                "message": "New message in appointment"
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket, "appointment", str(appointment_id))
        await manager.broadcast_to_appointment(appointment_id, f"User left appointment {appointment_id} chat")


@app.websocket("/ws/admin")
async def websocket_admin_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for admin real-time notifications - required by technical specs
    """
    await manager.connect(websocket, "admin")
    try:
        while True:
            # Keep connection alive and handle any admin-specific messages
            data = await websocket.receive_text()
            message_data = json.loads(data)

            if message_data.get("type") == "ping":
                await manager.send_personal_message(
                    json.dumps(
                        {"type": "pong", "timestamp": datetime.now().isoformat()}),
                    websocket
                )
    except WebSocketDisconnect:
        manager.disconnect(websocket, "admin")


@app.websocket("/ws/messages/{appointment_id}")
async def websocket_messages_endpoint(websocket: WebSocket, appointment_id: int):
    """
    Dedicated WebSocket endpoint for messages - required by technical specs
    """
    await manager.connect(websocket, "appointment", str(appointment_id))
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)

            # Broadcast to appointment participants
            await manager.broadcast_to_appointment(appointment_id, data)

            # Notify admins of message activity
            await manager.notify_admins("message_activity", {
                "appointment_id": appointment_id,
                "sender_id": message_data.get("sender_id"),
                "message_preview": message_data.get("message", "")[:50] + "..." if len(message_data.get("message", "")) > 50 else message_data.get("message", "")
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket, "appointment", str(appointment_id))


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

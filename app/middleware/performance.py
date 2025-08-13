import gzip
import io
import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse
from starlette.types import ASGIApp
import json

logger = logging.getLogger(__name__)

class CompressionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, minimum_size: int = 1000):
        super().__init__(app)
        self.minimum_size = minimum_size
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Only compress if client accepts gzip
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" not in accept_encoding:
            return response
        
        # Only compress JSON responses larger than minimum_size
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            return response
        
        # Get response body
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk
        
        # Check if worth compressing
        if len(response_body) < self.minimum_size:
            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
        
        # Compress the response
        compressed_body = gzip.compress(response_body)
        
        # Update headers
        headers = dict(response.headers)
        headers["content-encoding"] = "gzip"
        headers["content-length"] = str(len(compressed_body))
        
        return Response(
            content=compressed_body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type
        )

class PerformanceLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, slow_request_threshold: float = 1.0):
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request start for auth endpoints
        if request.url.path.startswith("/auth"):
            logger.info(f"AUTH REQUEST: {request.method} {request.url.path}")
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        
        # Log slow requests
        if process_time > self.slow_request_threshold:
            logger.warning(
                f"SLOW REQUEST: {request.method} {request.url.path} "
                f"took {process_time:.2f}s"
            )
        
        # Log auth response times
        if request.url.path.startswith("/auth"):
            logger.info(
                f"AUTH RESPONSE: {request.method} {request.url.path} "
                f"status={response.status_code} time={process_time:.3f}s"
            )
        
        # Add performance header
        response.headers["X-Process-Time"] = str(process_time)
        
        return response

class CacheControlMiddleware(BaseHTTPMiddleware):
    """Add cache control headers for better client-side caching"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.cache_rules = {
            "/auth/check-auth": "no-cache",  # Always validate auth
            "/auth/login": "no-cache, no-store, must-revalidate",
            "/auth/logout": "no-cache, no-store, must-revalidate",
            "/auth/signup": "no-cache, no-store, must-revalidate",
        }
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        path = request.url.path
        
        # Apply cache control rules
        cache_control = self.cache_rules.get(path)
        if cache_control:
            response.headers["Cache-Control"] = cache_control
        
        # Add security headers
        if path.startswith("/auth"):
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
        
        return response
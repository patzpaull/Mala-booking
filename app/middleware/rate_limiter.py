# app/middleware/rate_limiter.py

from fastapi import FastAPI, Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from time import time
from collections import defaultdict

class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 5, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clients = defaultdict(list)
    
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        current_time = time()
        request_times = self.clients[client_ip]
        
        while request_times and request_times[0] < current_time - self.window_seconds:
            request_times.pop(0)
        
        if len(request_times) >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later."
            )
        
        request_times.append(current_time)
        response = await call_next(request)
        return response
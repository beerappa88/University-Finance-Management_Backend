# middleware.py
"""
Middleware for security headers, permission context, and audit logging.
"""
from typing import Callable
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.core.rbac import PermissionCache
from app.core.logging import logger
from app.core.config import settings
from app.models.user import User
from uuid import UUID
from datetime import datetime, timedelta
import json

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    
    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response

class PermissionContextMiddleware(BaseHTTPMiddleware):
    """Add user permission context to request state."""
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Add user permissions to request state if user is authenticated
        user: User = getattr(request.state, 'user', None)
        if user:
            try:
                request.state.user_permissions = await PermissionCache.get_user_permissions(
                    user.id, 
                    user.role
                )
                request.state.user_role = user.role
                request.state.user_department_id = user.department_id
                logger.debug(f"Added permission context for user {user.username}")
            except Exception as e:
                logger.error(f"Error getting user permissions: {e}")
        
        response = await call_next(request)
        return response

class AuditMiddleware(BaseHTTPMiddleware):
    """Audit middleware for logging security events."""
    
    async def dispatch(self, request: Request, call_next: Callable):
        start_time = datetime.utcnow()
        
        # Get client info
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")
        
        # Get user if available
        user: User = getattr(request.state, 'user', None)
        user_id = user.id if user else None
        
        response = await call_next(request)
        
        # Calculate request duration
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        # Log request completion
        logger.info(
            f"Request: {request.method} {request.url.path} | "
            f"Status: {response.status_code} | "
            f"Duration: {duration:.3f}s | "
            f"User: {user_id} | "
            f"IP: {client_ip}"
        )
        
        # Log slow requests
        if duration > 2.0:
            logger.warning(
                f"Slow request detected: {request.method} {request.url.path} | "
                f"Duration: {duration:.3f}s | "
                f"User: {user_id} | "
                f"IP: {client_ip}"
            )
        
        # Log security-related status codes
        if response.status_code in [401, 403, 404]:
            logger.warning(
                f"Security status code: {response.status_code} | "
                f"Path: {request.url.path} | "
                f"User: {user_id} | "
                f"IP: {client_ip}"
            )
        
        return response

# Removed RateLimitMiddleware class
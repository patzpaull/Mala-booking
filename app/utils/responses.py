"""
Standardized API response wrapper utilities
"""
from typing import Any, Optional, Dict
from pydantic import BaseModel
from fastapi.responses import JSONResponse


class StandardResponse(BaseModel):
    """Standard API response format"""
    status: str = "success"
    code: int = 200
    message: Optional[str] = None
    data: Optional[Any] = None
    details: Optional[Dict[str, Any]] = None


def success_response(
    data: Any = None, 
    message: str = "Request successful", 
    code: int = 200,
    details: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """Create a standardized success response"""
    response_data = StandardResponse(
        status="success",
        code=code,
        message=message,
        data=data,
        details=details
    )
    return JSONResponse(
        status_code=code,
        content=response_data.dict(exclude_none=True)
    )


def error_response(
    message: str,
    code: int = 400,
    details: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """Create a standardized error response"""
    response_data = StandardResponse(
        status="error",
        code=code,
        message=message,
        details=details
    )
    return JSONResponse(
        status_code=code,
        content=response_data.dict(exclude_none=True)
    )


def created_response(
    data: Any,
    message: str = "Resource created successfully"
) -> JSONResponse:
    """Create a standardized 201 created response"""
    return success_response(data=data, message=message, code=201)


def no_content_response(
    message: str = "Operation completed successfully"
) -> JSONResponse:
    """Create a standardized 204 no content response"""
    return success_response(message=message, code=204)
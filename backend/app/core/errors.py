from typing import Any, Optional
from fastapi import Request, status  # type: ignore
from fastapi.responses import JSONResponse  # type: ignore
from fastapi.exceptions import RequestValidationError  # type: ignore
from starlette.exceptions import HTTPException as StarletteHTTPException  # type: ignore

class PlatformException(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Any] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

class NotFoundException(PlatformException):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            code="NOT_FOUND",
            message=f"{resource} '{identifier}' was not found",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource": resource, "identifier": identifier},
        )

class UnauthorizedException(PlatformException):
    def __init__(self, message: str = "Invalid or missing authentication credentials"):
        super().__init__(
            code="UNAUTHORIZED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

class ForbiddenException(PlatformException):
    def __init__(self, message: str = "You do not have permission to access this resource"):
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )

class ConflictException(PlatformException):
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            code="CONFLICT",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )

async def platform_exception_handler(request: Request, exc: Any) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )

async def http_exception_handler(request: Request, exc: Any) -> JSONResponse:
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        500: "INTERNAL_SERVER_ERROR",
    }
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code_map.get(exc.status_code, "HTTP_ERROR"),
                "message": exc.detail or "An error occurred",
                "details": {},
            }
        },
    )

async def validation_exception_handler(request: Request, exc: Any) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Input validation failed",
                "details": exc.errors(),
            }
        },
    )

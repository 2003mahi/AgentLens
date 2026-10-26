from fastapi import FastAPI  # type: ignore
from fastapi.exceptions import RequestValidationError  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from starlette.exceptions import HTTPException as StarletteHTTPException  # type: ignore

from backend.app.core.config import settings
from backend.app.core.errors import (
    PlatformException,
    platform_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from backend.app.db.base import Base
from backend.app.db.session import engine
from backend.app.db import models  # Ensure all models are registered
from backend.app.api.v1 import (
    health,
    datasets,
    agent_configs,
    experiments,
    runs,
)

# Initialize database schema tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# CORS – allow frontend origins during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers for consistent errors
app.add_exception_handler(PlatformException, platform_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Health router at root for legacy compatibility
app.include_router(health.router)

# Versioned API routes
app.include_router(health.router, prefix=settings.API_V1_STR)
app.include_router(datasets.router, prefix=settings.API_V1_STR)
app.include_router(agent_configs.router, prefix=settings.API_V1_STR)
app.include_router(experiments.router, prefix=settings.API_V1_STR)
app.include_router(runs.router, prefix=settings.API_V1_STR)

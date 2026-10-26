from fastapi import APIRouter
from sqlalchemy import text
from backend.app.db.session import engine

router = APIRouter(prefix="/health", tags=["health"])

@router.get("")
def health_check():
    return {"status": "ok"}

@router.get("/live")
def health_live():
    return {"status": "ok", "live": True}

@router.get("/ready")
def health_ready():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "ok" if db_status == "healthy" else "degraded",
        "database": db_status,
        "ready": db_status == "healthy",
    }

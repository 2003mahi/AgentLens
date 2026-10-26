import os
from dotenv import load_dotenv  # type: ignore
from pydantic import BaseModel  # type: ignore

# Automatically load .env from project root or current working directory
load_dotenv()

class Settings(BaseModel):
    PROJECT_NAME: str = "AI Agent Evaluation Platform"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./evaluation_platform.db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-insecure-secret-key-change-in-prod")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    def __init__(self, **data):
        super().__init__(**data)
        # Normalize postgresql:// to postgresql+psycopg2:// if psycopg2 is installed
        if self.DATABASE_URL.startswith("postgresql://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

settings = Settings()



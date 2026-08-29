"""
Application configuration.

Loads settings from backend/.env using python-dotenv.
Single source of configuration — do not create duplicates.
"""

import os
from dotenv import load_dotenv

# Load .env from backend directory
_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(_env_path)


class Settings:
    """Application settings loaded from environment variables."""

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ulpin_db"
    )
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Storage paths (relative to backend/)
    STORAGE_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage")
    UPLOAD_DIR: str = os.path.join(STORAGE_DIR, "uploads")
    MODEL_DIR: str = os.path.join(STORAGE_DIR, "models")


settings = Settings()

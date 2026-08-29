"""
Database engine and session factory.

Single SQLAlchemy engine connected to PostgreSQL/PostGIS.
Do NOT create duplicate engines or session factories elsewhere.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    FastAPI dependency that provides a database session.

    The session is created at the start of the request and closed
    at the end. Transactions are managed explicitly by the caller —
    the session does NOT auto-commit.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

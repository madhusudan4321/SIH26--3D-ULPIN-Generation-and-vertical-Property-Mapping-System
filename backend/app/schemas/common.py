"""
Common Pydantic schemas shared across endpoints.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class GeometryOut(BaseModel):
    """GeoJSON geometry representation for API responses."""
    type: str
    coordinates: list


class TimestampMixin(BaseModel):
    """Mixin for created_at / updated_at fields."""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str
    detail: Optional[str] = None

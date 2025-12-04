"""
Pydantic schemas for departments.

This module defines the request and response schemas for department-related
API endpoints using Pydantic models.
"""

from typing import Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DepartmentBase(BaseModel):
    """Base schema for department data."""
    
    name: str
    code: str
    description: Optional[str] = None


class DepartmentCreate(DepartmentBase):
    """Schema for creating a new department."""
    
    pass


class DepartmentUpdate(BaseModel):
    """Schema for updating a department."""
    
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None


class Department(DepartmentBase):
    """Schema for department response data."""
    
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        """Configuration for the Department schema."""
        
        from_attribute = True
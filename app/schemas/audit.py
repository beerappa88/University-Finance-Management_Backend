# app/schemas/audit.py
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True 


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int


class AuditLogsResponse(BaseModel):
    results: List[AuditLogResponse]
    pagination: PaginationMeta
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from typing import Any

def make_json_serializable(data: Any) -> Any:
    """
    Recursively convert non-serializable values (UUID, Decimal, datetime) to JSON-serializable formats.
    """
    if isinstance(data, dict):
        return {str(k): make_json_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [make_json_serializable(v) for v in data]
    elif isinstance(data, UUID):
        return str(data)
    elif isinstance(data, Decimal):
        return float(data)
    elif isinstance(data, (datetime, date)):
        return data.isoformat()
    return data

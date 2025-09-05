from typing import Optional, Any, Dict, List, Union, TypeVar, Generic
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import DeclarativeBase
from pydantic import BaseModel
from app.core.logging import logger

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """Response wrapper for paginated results."""
    
    items: List[T]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool
    next_page: Optional[int] = None
    prev_page: Optional[int] = None

class PaginationParams:
    """Parameters for pagination."""
    
    def __init__(
        self, 
        page: int = 1, 
        size: int = 10, 
        search: Optional[str] = None,
        sort_by: str = "id", 
        sort_order: str = "asc"
    ):
        self.page = page
        self.size = size
        self.search = search
        self.sort_by = sort_by
        self.sort_order = sort_order

async def paginate_query(
    db: AsyncSession,
    query: Any,
    pagination: PaginationParams,
    count_query: Any = None,
    model: Optional[DeclarativeBase] = None,
    use_scalars: bool = True
) -> PaginatedResponse[Any]:
    """
    Paginate a query with sorting and support for both ORM models and column selects.
    
    Args:
        db: Database session
        query: SQLAlchemy select query
        pagination: Pagination parameters
        count_query: Optional count query
        model: Model for sorting
        use_scalars: If True, use .scalars(); if False, use .fetchall() for Row objects
    """
    try:
        # Apply sorting
        if model and hasattr(model, pagination.sort_by):
            sort_col = getattr(model, pagination.sort_by)
            if pagination.sort_order == "desc":
                query = query.order_by(sort_col.desc())
            else:
                query = query.order_by(sort_col.asc())
        else:
            logger.debug(f"Skipping sort: invalid field '{pagination.sort_by}' for model {model}")
        
        offset = (pagination.page - 1) * pagination.size
        paginated_query = query.offset(offset).limit(pagination.size)
        
        # Execute count
        if count_query is None:
            count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar()
        
        # Execute main query
        result = await db.execute(paginated_query)
        
        # Choose result extraction method
        if use_scalars:
            items = result.scalars().all()
        else:
            items = result.fetchall()  # For Row objects from column selects
        
        # Calculate metadata
        pages = (total + pagination.size - 1) // pagination.size if total else 0
        has_next = pagination.page < pages
        has_prev = pagination.page > 1
        
        # Calculate next_page and prev_page
        next_page = pagination.page + 1 if has_next else None
        prev_page = pagination.page - 1 if has_prev else None
        
        return PaginatedResponse(
            items=items,
            total=total,
            page=pagination.page,
            size=pagination.size,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev,
            next_page=next_page,
            prev_page=prev_page
        )
    except Exception as e:
        logger.error(f"Error in paginate_query: {str(e)}", exc_info=True)
        raise

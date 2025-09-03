"""
Service layer for department operations.

This module contains the business logic for department-related operations,
abstracting away the database operations from the API endpoints.
"""

from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.logging import logger
from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.db.audit import log_action_async
from uuid import UUID 


class DepartmentService:
    """Service class for department operations."""
    
    @staticmethod
    async def create(
        db: AsyncSession, 
        department_in: DepartmentCreate,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Department:
        """
        Create a new department.
        
        Args:
            db: Database session
            department_in: Department creation data
            user_id: ID of the user performing the action
            ip_address: IP address of the user
            user_agent: User agent string
            
        Returns:
            Created department
        """
        logger.info(f"Creating new department: {department_in.name}")
        
        # Check if department code already exists
        existing_department = await DepartmentService.get_by_code(db, department_in.code)
        if existing_department:
            logger.warning(
                f"Department code already exists: {department_in.code}"
            )
            raise ValueError(
                f"Department code already exists: {department_in.code}"
            )
        
        department = Department(**department_in.dict())
        db.add(department)
        await db.commit()
        await db.refresh(department)
        
        # Log the action
        await log_action_async(
            db,
            action="CREATE",
            resource_type="DEPARTMENT",
            resource_id=str(department.id),
            details={
                "name": department.name,
                "code": department.code
            },
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        logger.info(f"Created department with ID: {department.id}")
        return department
    
    @staticmethod
    async def get_by_id(
        db: AsyncSession, 
        department_id: UUID
    ) -> Optional[Department]:
        """
        Get a department by ID.
        
        Args:
            db: Database session
            department_id: Department ID
            
        Returns:
            Department if found, None otherwise
        """
        logger.debug(f"Getting department by ID: {department_id}")
        
        result = await db.execute(
            select(Department).where(Department.id == department_id)
        )
        return result.scalars().first()
    
    @staticmethod
    async def get_by_code(
        db: AsyncSession, 
        code: str
    ) -> Optional[Department]:
        """
        Get a department by code.
        
        Args:
            db: Database session
            code: Department code
            
        Returns:
            Department if found, None otherwise
        """
        logger.debug(f"Getting department by code: {code}")
        
        result = await db.execute(
            select(Department).where(Department.code == code)
        )
        return result.scalars().first()
    
    @staticmethod
    async def get_all(
        db: AsyncSession, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Department]:
        """
        Get all departments with pagination.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of departments
        """
        logger.debug(f"Getting all departments, skip={skip}, limit={limit}")
        
        result = await db.execute(
            select(Department).offset(skip).limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def update(
        db: AsyncSession, 
        department_id: UUID, 
        department_in: DepartmentUpdate,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[Department]:
        """
        Update a department.
        
        Args:
            db: Database session
            department_id: Department ID
            department_in: Department update data
            user_id: ID of the user performing the action
            ip_address: IP address of the user
            user_agent: User agent string
            
        Returns:
            Updated department if found, None otherwise
        """
        logger.info(f"Updating department with ID: {department_id}")
        
        # Check if department exists
        department = await DepartmentService.get_by_id(db, department_id)
        if not department:
            logger.warning(f"Department not found for update, ID: {department_id}")
            return None
        
        # If updating code, check if it's already used by another department
        if department_in.code and department_in.code != department.code:
            existing_department = await DepartmentService.get_by_code(db, department_in.code)
            if existing_department:
                logger.warning(
                    f"Department code already exists: {department_in.code}"
                )
                raise ValueError(
                    f"Department code already exists: {department_in.code}"
                )
        
        # Store original values for audit log
        original_values = {
            "name": department.name,
            "code": department.code,
            "description": department.description
        }
        
        update_data = department_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(department, field, value)
        
        await db.commit()
        await db.refresh(department)
        
        # Log the action
        changes = {}
        for field in original_values:
            if field in update_data and str(original_values[field]) != str(getattr(department, field)):
                changes[field] = {
                    "old": original_values[field],
                    "new": getattr(department, field)
                }
        
        if changes:
            await log_action_async(
                db,
                action="UPDATE",
                resource_type="DEPARTMENT",
                resource_id=str(department.id),
                details=changes,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
        
        logger.info(f"Updated department: {department.name}")
        return department
    
    @staticmethod
    async def delete(
        db: AsyncSession, 
        department_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Delete a department.
        
        Args:
            db: Database session
            department_id: Department ID
            user_id: ID of the user performing the action
            ip_address: IP address of the user
            user_agent: User agent string
            
        Returns:
            True if department was deleted, False otherwise
        """
        logger.info(f"Deleting department with ID: {department_id}")
        
        department = await DepartmentService.get_by_id(db, department_id)
        if not department:
            logger.warning(f"Department not found for deletion, ID: {department_id}")
            return False
        
        # Store values for audit log
        department_values = {
            "id": department.id,
            "name": department.name,
            "code": department.code,
            "description": department.description
        }
        
        await db.delete(department)
        await db.commit()
        
        # Log the action
        await log_action_async(
            db,
            action="DELETE",
            resource_type="DEPARTMENT",
            resource_id=str(department.id),
            details=department_values,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        logger.info(f"Deleted department: {department.name}")
        return True
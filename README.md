
## Architectural Choices Explained

### Project Structure
The project follows a clear separation of concerns with dedicated directories for different components:
- `core/`: Contains configuration, security, and logging utilities that are fundamental to the application.
- `models/`: Contains SQLAlchemy models that define the database schema.
- `schemas/`: Contains Pydantic schemas for request/response validation and serialization.
- `services/`: Contains the business logic layer, abstracting database operations from API endpoints.
- `routers/`: Contains API endpoints that handle HTTP requests and responses.
- `utils/`: Contains helper functions that can be reused across the application.

This structure promotes maintainability and scalability by clearly separating responsibilities.

### Dependency Management with Poetry
Poetry was chosen for dependency management because it provides:
- A single file for managing both dependencies and dev dependencies
- Reliable dependency resolution
- Virtual environment management
- Lock files for reproducible builds

### Async SQLAlchemy with PostgreSQL
Using async SQLAlchemy with asyncpg driver provides:
- Better performance for I/O-bound operations
- Non-blocking database operations
- Integration with FastAPI's async capabilities
- Support for modern Python async/await syntax

### Environment-based Configuration
The application uses different configurations for development, production, and testing environments:
- Allows for environment-specific settings without code changes
- Supports different database URLs, logging levels, and security settings
- Uses Pydantic for configuration validation and type checking
- Loads configuration from .env files for easy deployment

### Service Layer
The service layer abstracts business logic from the API endpoints:
- Promotes code reuse by centralizing business logic
- Makes the application easier to test by isolating business rules
- Provides a clear separation between data access and API handling
- Handles complex operations like budget updates when transactions are created/modified

### Comprehensive Logging
The application uses loguru for advanced logging:
- Provides different configurations for development and production
- Supports structured logging with contextual information
- Allows for easy filtering and analysis of logs
- Integrates well with async applications

### Alembic for Migrations
Alembic provides a robust way to manage database schema changes:
- Supports both manual and automatic migration generation
- Provides version control for database schema
- Allows for easy rollback of changes
- Integrates well with SQLAlchemy models

### Security Considerations
The application includes several security features:
- Password hashing using bcrypt
- JWT token authentication infrastructure
- Input validation using Pydantic schemas
- CORS middleware configuration
- Protection against common web vulnerabilities

### API Design
The API follows RESTful principles:
- Clear resource naming (departments, budgets, transactions)
- Proper HTTP methods (GET, POST, PUT, DELETE)
- Appropriate HTTP status codes
- Consistent response formats
- Comprehensive API documentation with FastAPI's automatic OpenAPI generation

This architecture provides a solid foundation for a scalable, secure, and maintainable university finance management system. The clear separation of concerns makes it easy to extend and maintain, while the use of modern Python async features ensures good performance.


## Authentication and Authorization

The API uses JWT (JSON Web Tokens) for authentication and role-based authorization.

### User Roles

- **admin**: Full access to all resources and user management
- **finance_manager**: Can manage departments, budgets, and transactions
- **viewer**: Read-only access to all resources

### Authentication Flow

1. Register a user with `POST /auth/register`
2. Obtain a JWT token with `POST /auth/token`
3. Include the token in the Authorization header for protected endpoints:



### Protected Endpoints

All endpoints except health checks and user registration require authentication. Some endpoints require specific roles:

- **Finance Manager Role Required**:
  - `POST /departments/`
  - `PUT /departments/{id}`
  - `DELETE /departments/{id}`
  - `POST /budgets/`
  - `PUT /budgets/{id}`
  - `DELETE /budgets/{id}`
  - `POST /transactions/`
  - `PUT /transactions/{id}`
  - `DELETE /transactions/{id}`

- **Viewer Role or Higher Required**:
  - `GET /departments/`
  - `GET /departments/{id}`
  - `GET /budgets/`
  - `GET /budgets/{id}`
  - `GET /transactions/`
  - `GET /transactions/{id}`

## Testing

The application includes comprehensive tests for all components.

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=app

# Run specific test file
poetry run pytest tests/test_auth.py

# Run tests with verbose output
poetry run pytest -v



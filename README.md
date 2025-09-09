## University Finance API

A scalable, secure, and maintainable API for managing university financial operations, built with FastAPI, async SQLAlchemy, and PostgreSQL.

---

## Architectural Choices Explained

### Project Structure
The project follows a clear separation of concerns with dedicated directories for different components:
- `core/`: Configuration, security, and logging utilities.
- `models/`: SQLAlchemy models for database schema.
- `schemas/`: Pydantic schemas for request/response validation.
- `services/`: Business logic layer, abstracting database operations.
- `routers/`: API endpoints for HTTP requests and responses.
- `utils/`: Helper functions for reuse across the application.

This structure promotes maintainability and scalability.

### Dependency Management with Poetry
Poetry is used for dependency management:
- Single file for dependencies and dev dependencies
- Reliable dependency resolution and virtual environment management
- Lock files for reproducible builds

### Async SQLAlchemy with PostgreSQL
- Non-blocking database operations using asyncpg
- Integration with FastAPI's async capabilities
- Modern Python async/await syntax

### Environment-based Configuration
- Supports development, production, and testing environments
- Loads configuration from `.env` files
- Uses Pydantic for validation and type checking

### Service Layer
- Centralizes business logic for code reuse and easier testing
- Separates data access from API handling

### Comprehensive Logging
- Uses loguru for structured, contextual logging
- Configurable for development and production

### Alembic for Migrations
- Manages database schema changes with version control
- Supports rollback and integrates with SQLAlchemy models

### Security Considerations
- Password hashing with bcrypt
- JWT authentication and role-based authorization
- Input validation with Pydantic
- CORS middleware and protection against common web vulnerabilities

### API Design
- RESTful principles: clear resource naming, proper HTTP methods, status codes, and consistent response formats
- Automatic OpenAPI documentation via FastAPI

---

## Getting Started

### Prerequisites
- Python 3.9–3.12
- PostgreSQL database
- Redis server (for caching and session management)
- Poetry (for dependency management)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/university-finance-api.git
cd university-finance-api

# Install dependencies
poetry install

# Copy environment variables template and configure
cp .env.example .env
# Edit .env with your database, Redis, and SMTP credentials

# Run database migrations
poetry run alembic upgrade head

# Start the application
poetry run uvicorn app.main:app --reload
```

### Docker Setup

A `docker-compose.yml` is provided for running Redis locally:

```bash
docker-compose up -d redis
```

---

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

   ```
   Authorization: Bearer <your_token>
   ```

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

---

## Testing

Comprehensive tests are included for all components.

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
```

---

## API Documentation

Interactive API docs are available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Contributing

1. Fork the repository and create your branch.
2. Make your changes and add tests.
3. Run `poetry run pytest` to ensure all tests pass.
4. Submit a pull request with a clear description.

---

## License

This project is licensed under the MIT License.
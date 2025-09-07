# config.py
"""
Configuration module for the application.
Handles environment-specific settings using Pydantic v2 and pydantic-settings.
"""
from typing import Optional, List, Annotated
from pydantic import BeforeValidator, AfterValidator
from enum import Enum
from pydantic import Field, field_validator, BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"

class LoggingSettings(BaseModel):
    level: str = "INFO"
    format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
    file_enabled: bool = True
    file_path: str = "logs/app.log"

class APISettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    prefix: str = "/api"
    version: str = "1.0.0"
    title: str = "University Finance Management API"
    description: str = "A scalable, secure, and maintainable API for university finance management"

class DatabaseSettings(BaseModel):
    url: str
    pool_size: int = 20
    max_overflow: int = 30
    pool_recycle: int = 3600

class RedisSettings(BaseModel):
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[SecretStr] = None
    max_connections: int = 50
    @property
    def password_str(self) -> Optional[str]:
        """Return the password as a string for Redis connection."""
        return self.password.get_secret_value() if self.password else None

class SecuritySettings(BaseModel):
    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_min_length: int = 8
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    @property
    def secret_key_str(self) -> str:
        """Return the secret key as a string for JWT operations."""
        return self.secret_key.get_secret_value()

class EmailSettings(BaseModel):
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    use_tls: bool = True
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    from_email: str = "noreply@university.edu"
    @property
    def password_str(self) -> Optional[str]:
        """Return the password as a string for SMTP connection."""
        return self.password.get_secret_value() if self.password else None

class CacheSettings(BaseModel):
    ttl: int = 3600
    enabled: bool = True

class Settings(BaseSettings):
    """Main settings class with environment-specific configurations."""
    # Environment
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    
    # API
    api_title: str = "University Finance Management API"
    api_description: str = "A scalable, secure, and maintainable API for university finance management"
    api_version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Database
    database_url: str
    pool_size: int = 20
    max_overflow: int = 30
    pool_recycle: int = 3600
    
    # Security
    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_min_length: int = 8
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    
    # Logging
    log_level: str = "INFO"
    log_format: str = Field(default="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}")
    log_file_enabled: bool = True
    log_file_path: str = "logs/app.log"
    
    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[SecretStr] = None
    redis_max_connections: int = 50
    
    # Cache
    cache_ttl: int = 3600
    enable_cache: bool = True
    
    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_use_tls: bool = True
    smtp_username: Optional[str] = None
    smtp_password: Optional[SecretStr] = None
    smtp_from_email: str = "noreply@university.edu"
    
    # Frontend
    frontend_urls_raw: str = Field(
        default="http://localhost:3000",
        alias="FRONTEND_URLS",
        exclude=True,
    )
    password_reset_token_expire_minutes: int = 60
    
    # Feature flags
    enable_audit_logs: bool = True
    enable_2fa: bool = True
    enable_email_notifications: bool = True
    
    # Validators
    @field_validator("debug")
    @classmethod
    def debug_not_in_production(cls, v, info):
        env = info.data.get("environment")
        if v and env == Environment.PRODUCTION:
            raise ValueError("Debug mode should not be enabled in production")
        return v
    
    @property
    def frontend_urls(self) -> list[str]:
        """Comma-separated frontend URLs from .env, parsed into a list."""
        urls = [url.strip() for url in self.frontend_urls_raw.split(",") if url.strip()]
        # Optional: Validate URLs
        from urllib.parse import urlparse
        for url in urls:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError(f"Invalid URL in frontend_urls: {url}")
        return urls
    
    @field_validator("smtp_password")
    @classmethod
    def validate_smtp_password(cls, v, info):
        env = info.data.get("environment")
        if env == Environment.PRODUCTION and not v:
            raise ValueError("SMTP password must be set in production")
        return v
    
    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v):
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("Invalid database URL format")
        return v
    
    # Sub-settings via properties
    @property
    def api(self) -> APISettings:
        return APISettings(
            host=self.host,
            port=self.port,
            title=self.api_title,
            description=self.api_description,
            version=self.api_version,
        )
    
    @property
    def logging(self) -> LoggingSettings:
        return LoggingSettings(
            level=self.log_level,
            format=self.log_format,
            file_enabled=self.log_file_enabled,
            file_path=self.log_file_path,
        )
    
    @property
    def database(self) -> DatabaseSettings:
        return DatabaseSettings(
            url=self.database_url,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_recycle=self.pool_recycle,
        )
    
    @property
    def redis(self) -> RedisSettings:
        return RedisSettings(
            host=self.redis_host,
            port=self.redis_port,
            db=self.redis_db,
            password=self.redis_password,
            max_connections=self.redis_max_connections,
        )
    
    @property
    def security(self) -> SecuritySettings:
        return SecuritySettings(
            secret_key=self.secret_key,
            algorithm=self.algorithm,
            access_token_expire_minutes=self.access_token_expire_minutes,
            refresh_token_expire_days=self.refresh_token_expire_days,
            password_min_length=self.password_min_length,
            max_login_attempts=self.max_login_attempts,
            lockout_duration_minutes=self.lockout_duration_minutes,
        )
    
    @property
    def email(self) -> EmailSettings:
        return EmailSettings(
            smtp_host=self.smtp_host,
            smtp_port=self.smtp_port,
            use_tls=self.smtp_use_tls,
            username=self.smtp_username,
            password=self.smtp_password,
            from_email=self.smtp_from_email,
        )
    
    @property
    def cache(self) -> CacheSettings:
        return CacheSettings(
            ttl=self.cache_ttl,
            enabled=self.enable_cache,
        )
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",
        secrets_dir="/run/secrets",  # For Docker secrets
    )

class DevelopmentSettings(Settings):
    debug: bool = True
    log_level: str = "DEBUG"

class ProductionSettings(Settings):
    debug: bool = False
    log_level: str = "INFO"
    
    @field_validator("smtp_password")
    @classmethod
    def validate_smtp_password(cls, v):
        if not v:
            raise ValueError("SMTP password is required in production")
        return v

class TestingSettings(Settings):
    database_url: str = "sqlite+aiosqlite:///:memory:"
    debug: bool = True
    log_level: str = "DEBUG"
    redis_db: int = 1
    enable_cache: bool = False

def get_settings() -> Settings:
    """Factory to return environment-specific settings."""
    env = Settings().environment
    if env == Environment.PRODUCTION:
        return ProductionSettings()
    elif env == Environment.TESTING:
        return TestingSettings()
    return DevelopmentSettings()

# Global settings instance
settings = get_settings()

"""
Security utilities for the application.
This module provides functions for password hashing and verification,
JWT token creation and verification, and two-factor authentication.
"""
import pyotp
import base64
import json
import secrets
import string
from typing import Optional, Union, Any, Dict
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.core.logging import logger
from uuid import UUID

# Password context for hashing and verification
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class TokenManager:
    """Enhanced JWT token management."""
    
    @staticmethod
    def create_access_token(
        subject: Union[str, Any], 
        expires_delta: Optional[timedelta] = None,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a JWT access token with additional claims.
        
        Args:
            subject: The subject to encode in the token (usually user ID)
            expires_delta: Optional expiration time delta
            additional_claims: Optional additional claims to include
            
        Returns:
            Encoded JWT token
        """
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.security.access_token_expire_minutes
            )
        
        to_encode = {
            "exp": expire,
            "iat": datetime.utcnow(),
            "sub": str(subject),
            "type": "access",
            "jti": secrets.token_hex(16),  # JWT ID for revocation
        }
        
        if additional_claims:
            to_encode.update(additional_claims)
        
        # Use the string representation of the secret key
        encoded_jwt = jwt.encode(
            to_encode, 
            settings.security.secret_key_str,  # Use the string property
            algorithm=settings.security.algorithm
        )
        
        logger.debug(f"Created access token for subject: {subject}")
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(subject: Union[str, Any]) -> str:
        """
        Create a JWT refresh token.
        
        Args:
            subject: The subject to encode in the token (usually user ID)
            
        Returns:
            Encoded JWT refresh token
        """
        expire = datetime.utcnow() + timedelta(
            days=settings.security.refresh_token_expire_days
        )
        
        to_encode = {
            "exp": expire,
            "iat": datetime.utcnow(),
            "sub": str(subject),
            "type": "refresh",
            "jti": secrets.token_hex(16),
        }
        
        encoded_jwt = jwt.encode(
            to_encode, 
            settings.security.secret_key_str,  # Use the string property
            algorithm=settings.security.algorithm
        )
        
        logger.debug(f"Created refresh token for subject: {subject}")
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """
        Verify and decode JWT token.
        
        Args:
            token: JWT token to verify
            token_type: Expected token type ("access" or "refresh")
            
        Returns:
            Decoded token payload or None if invalid
        """
        try:
            payload = jwt.decode(
                token, 
                settings.security.secret_key_str,  # Use the string property
                algorithms=[settings.security.algorithm]
            )
            
            # Check token type
            if payload.get("type") != token_type:
                logger.warning(f"Invalid token type: expected {token_type}, got {payload.get('type')}")
                return None
            
            # Check expiration
            if datetime.utcnow() > datetime.fromtimestamp(payload["exp"]):
                logger.warning("Token expired")
                return None
            
            logger.debug(f"Token verified successfully for subject: {payload.get('sub')}")
            return payload
            
        except JWTError as e:
            logger.warning(f"JWT verification error: {e}")
            return None
    
    @staticmethod
    def decode_token_without_verification(token: str) -> Optional[Dict[str, Any]]:
        """
        Decode token without verification (for blacklisting purposes).
        
        Args:
            token: JWT token to decode
            
        Returns:
            Decoded token payload or None if invalid
        """
        try:
            payload = jwt.decode(
                token, 
                options={"verify_signature": False},
                algorithms=[settings.security.algorithm]
            )
            return payload
        except Exception as e:
            logger.warning(f"Token decode error: {e}")
            return None
    
    @staticmethod
    def is_token_expiring_soon(token: str, buffer_minutes: int = 5) -> bool:
        """
        Check if a token is about to expire.
        
        Args:
            token: JWT token to check
            buffer_minutes: Buffer time in minutes before expiration
            
        Returns:
            True if token is expiring soon, False otherwise
        """
        try:
            payload = jwt.decode(
                token, 
                options={"verify_signature": False},
                algorithms=[settings.security.algorithm]
            )
            
            exp_timestamp = payload.get("exp")
            if not exp_timestamp:
                return False
            
            expiration_time = datetime.fromtimestamp(exp_timestamp)
            buffer_time = datetime.utcnow() + timedelta(minutes=buffer_minutes)
            
            return expiration_time <= buffer_time
            
        except Exception as e:
            logger.warning(f"Token expiration check error: {e}")
            return True  # Assume it's expiring soon if we can't check

class PasswordManager:
    """Password management utilities."""
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against a hash.
        
        Args:
            plain_password: The plain text password
            hashed_password: The hashed password
            
        Returns:
            True if password matches hash, False otherwise
        """
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """
        Generate a password hash.
        
        Args:
            password: The plain text password
            
        Returns:
            Hashed password
        """
        try:
            return pwd_context.hash(password)
        except Exception as e:
            logger.error(f"Password hashing error: {e}")
            raise
    
    @staticmethod
    def is_password_strong(password: str) -> bool:
        """
        Check if password meets strength requirements.
        
        Args:
            password: Password to check
            
        Returns:
            True if password is strong enough
        """
        if len(password) < settings.security.password_min_length:
            return False
        
        # Check for at least one digit
        if not any(c.isdigit() for c in password):
            return False
        
        # Check for at least one uppercase letter
        if not any(c.isupper() for c in password):
            return False
        
        # Check for at least one lowercase letter
        if not any(c.islower() for c in password):
            return False
        
        # Check for at least one special character
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            return False
        
        return True

class TwoFactorAuth:
    """Two-factor authentication utilities."""
    
    @staticmethod
    def generate_totp_secret() -> str:
        """
        Generate a new TOTP secret.
        
        Returns:
            Base32 encoded TOTP secret
        """
        return pyotp.random_base32()
    
    @staticmethod
    def generate_totp_uri(secret: str, username: str) -> str:
        """
        Generate TOTP URI for QR code.
        
        Args:
            secret: TOTP secret
            username: Username
            
        Returns:
            TOTP URI for QR code
        """
        return pyotp.totp.TOTP(secret).provisioning_uri(
            name=username,
            issuer_name="University Finance System"
        )
    
    @staticmethod
    def verify_totp(secret: str, token: str) -> bool:
        """
        Verify TOTP token.
        
        Args:
            secret: TOTP secret
            token: TOTP token
            
        Returns:
            True if token is valid, False otherwise
        """
        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(token, valid_window=1)
        except Exception as e:
            logger.error(f"TOTP verification error: {e}")
            return False
    
    @staticmethod
    def generate_backup_codes() -> list:
        """
        Generate backup codes for 2FA.
        
        Returns:
            List of backup codes
        """
        codes = []
        for _ in range(10):
            code = ''.join(secrets.choice(string.digits) for _ in range(8))
            codes.append(code)
        
        logger.info("Generated new backup codes")
        return codes
    
    @staticmethod
    def verify_backup_code(backup_codes_str: str, code: str) -> bool:
        """
        Verify backup code.
        
        Args:
            backup_codes_str: JSON string of backup codes
            code: Code to verify
            
        Returns:
            True if code is valid, False otherwise
        """
        try:
            backup_codes = json.loads(backup_codes_str)
            if code in backup_codes:
                # Remove used backup code
                backup_codes.remove(code)
                logger.info("Backup code used successfully")
                return True
            return False
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Backup code verification error: {e}")
            return False
    
    @staticmethod
    def format_backup_codes(codes: list) -> str:
        """
        Format backup codes as JSON string.
        
        Args:
            codes: List of backup codes
            
        Returns:
            JSON string of backup codes
        """
        return json.dumps(codes)

class SecurityUtils:
    """General security utilities."""
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """
        Generate a secure random token.
        
        Args:
            length: Token length
            
        Returns:
            Secure random token
        """
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def generate_reset_token() -> str:
        """
        Generate a password reset token.
        
        Returns:
            Secure reset token
        """
        return SecurityUtils.generate_secure_token(32)
    
    @staticmethod
    def is_safe_url(url: str) -> bool:
        """
        Check if URL is safe (for redirects).
        
        Args:
            url: URL to check
            
        Returns:
            True if URL is safe
        """
        return url.startswith(('http://', 'https://')) and ' ' not in url
    
    @staticmethod
    def sanitize_input(input_string: str) -> str:
        """
        Sanitize user input to prevent XSS attacks.
        
        Args:
            input_string: Input string to sanitize
            
        Returns:
            Sanitized string
        """
        # Basic sanitization - in production, consider using a proper HTML sanitizer
        return input_string.replace('<', '&lt;').replace('>', '&gt;')

# Legacy function aliases for backward compatibility
def create_access_token(
    subject: Union[str, Any], 
    expires_delta: Optional[timedelta] = None
) -> str:
    """Legacy function for backward compatibility."""
    return TokenManager.create_access_token(subject, expires_delta)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Legacy function for backward compatibility."""
    return PasswordManager.verify_password(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Legacy function for backward compatibility."""
    return PasswordManager.get_password_hash(password)

def generate_totp_secret() -> str:
    """Legacy function for backward compatibility."""
    return TwoFactorAuth.generate_totp_secret()

def generate_totp_uri(secret: str, username: str) -> str:
    """Legacy function for backward compatibility."""
    return TwoFactorAuth.generate_totp_uri(secret, username)

def verify_totp(secret: str, token: str) -> bool:
    """Legacy function for backward compatibility."""
    return TwoFactorAuth.verify_totp(secret, token)

def generate_backup_codes() -> list:
    """Legacy function for backward compatibility."""
    return TwoFactorAuth.generate_backup_codes()

def verify_backup_code(backup_codes_str: str, code: str) -> bool:
    """Legacy function for backward compatibility."""
    return TwoFactorAuth.verify_backup_code(backup_codes_str, code)
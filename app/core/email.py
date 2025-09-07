"""
Email utilities for sending emails.
This module provides utilities for sending emails using SMTP.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings
from app.core.logging import logger

class EmailService:
    """Service for sending emails."""
    
    @staticmethod
    def send_password_reset_email(email: str, reset_token: str) -> bool:
        """
        Send a password reset email.
        
        Args:
            email: Recipient email address
            reset_token: Password reset token
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Create message
            message = MIMEMultipart()
            message["From"] = settings.SMTP_FROM_EMAIL
            message["To"] = email
            message["Subject"] = "University Finance System - Password Reset"
            
            # Create HTML body
            html = f"""
            <html>
            <body>
                <h2>Password Reset Request</h2>
                <p>You have requested to reset your password for the University Finance System.</p>
                <p>Please click the link below to reset your password:</p>
                <p><a href="{settings.FRONTEND_URLS[1]}/reset-password?token={reset_token}">Reset Password</a></p>
                <p>If you did not request this password reset, please ignore this email.</p>
                <p>This link will expire in 1 hour.</p>
                <p>Thank you,<br>University Finance System Team</p>
            </body>
            </html>
            """
            
            # Attach HTML body
            html_part = MIMEText(html, "html")
            message.attach(html_part)
            
            # Connect to SMTP server and send email
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(message)
            
            logger.info(f"Password reset email sent to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send password reset email to {email}: {str(e)}")
            return False
    
    @staticmethod
    def send_welcome_email(email: str, username: str) -> bool:
        """
        Send a welcome email to new users.
        
        Args:
            email: Recipient email address
            username: Username
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Create message
            message = MIMEMultipart()
            message["From"] = settings.SMTP_FROM_EMAIL
            message["To"] = email
            message["Subject"] = "Welcome to University Finance System"
            
            # Create HTML body
            html = f"""
            <html>
            <body>
                <h2>Welcome to University Finance System!</h2>
                <p>Dear {username},</p>
                <p>Your account has been successfully created in the University Finance System.</p>
                <p>You can now log in using your credentials to access the system.</p>
                <p>If you have any questions or need assistance, please contact the IT support team.</p>
                <p>Thank you,<br>University Finance System Team</p>
            </body>
            </html>
            """
            
            # Attach HTML body
            html_part = MIMEText(html, "html")
            message.attach(html_part)
            
            # Connect to SMTP server and send email
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(message)
            
            logger.info(f"Welcome email sent to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send welcome email to {email}: {str(e)}")
            return False
    
    @staticmethod
    def send_role_change_email(email: str, username: str, old_role: str, new_role: str) -> bool:
        """
        Send a role change notification email.
        
        Args:
            email: Recipient email address
            username: Username
            old_role: Previous role
            new_role: New role
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Create message
            message = MIMEMultipart()
            message["From"] = settings.SMTP_FROM_EMAIL
            message["To"] = email
            message["Subject"] = "University Finance System - Role Change Notification"
            
            # Create HTML body
            html = f"""
            <html>
            <body>
                <h2>Role Change Notification</h2>
                <p>Dear {username},</p>
                <p>Your role in the University Finance System has been changed.</p>
                <p><strong>Previous Role:</strong> {old_role}</p>
                <p><strong>New Role:</strong> {new_role}</p>
                <p>This change affects your permissions within the system. Please log in to review your updated access rights.</p>
                <p>If you believe this change was made in error, please contact the system administrator immediately.</p>
                <p>Thank you,<br>University Finance System Team</p>
            </body>
            </html>
            """
            
            # Attach HTML body
            html_part = MIMEText(html, "html")
            message.attach(html_part)
            
            # Connect to SMTP server and send email
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(message)
            
            logger.info(f"Role change notification sent to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send role change email to {email}: {str(e)}")
            return False
    
    @staticmethod
    def send_account_deletion_email(email: str, username: str) -> bool:
        """
        Send an account deletion notification email.
        
        Args:
            email: Recipient email address
            username: Username
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Create message
            message = MIMEMultipart()
            message["From"] = settings.SMTP_FROM_EMAIL
            message["To"] = email
            message["Subject"] = "University Finance System - Account Deletion Notification"
            
            # Create HTML body
            html = f"""
            <html>
            <body>
                <h2>Account Deletion Notification</h2>
                <p>Dear {username},</p>
                <p>Your account in the University Finance System has been deleted.</p>
                <p>If you believe this was done in error or have any questions about this action, please contact the system administrator immediately.</p>
                <p>Thank you,<br>University Finance System Team</p>
            </body>
            </html>
            """
            
            # Attach HTML body
            html_part = MIMEText(html, "html")
            message.attach(html_part)
            
            # Connect to SMTP server and send email
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(message)
            
            logger.info(f"Account deletion notification sent to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send account deletion email to {email}: {str(e)}")
            return False
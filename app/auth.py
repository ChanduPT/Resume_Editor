# app/auth.py
# Authentication endpoints and dependencies

from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
import logging
from datetime import datetime
import os

from app.database import get_db, User, authenticate_user, verify_password, create_user

logger = logging.getLogger(__name__)
security = HTTPBasic()
limiter = Limiter(key_func=get_remote_address)



# JWT authentication support
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "resume_jwt_secret_2025")
JWT_ALGORITHM = "HS256"
bearer_scheme = HTTPBearer(auto_error=False)  # Don't auto-error, allow fallback

def decode_jwt_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception as e:
        logger.warning(f"[AUTH] JWT decode failed: {e}")
        return None

async def get_current_user(
    db: Session = Depends(get_db),
    credentials: Optional[HTTPBasicCredentials] = Depends(security),
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
):
    """
    Dependency to get current authenticated user
    Supports both HTTP Basic Auth AND JWT Bearer tokens
    """
    # Try JWT Bearer token first (for new job scraper endpoints)
    if bearer and bearer.credentials:
        token = bearer.credentials
        payload = decode_jwt_token(token)
        if payload and "user_id" in payload:
            user_id = payload["user_id"].lower().strip()
            user = db.query(User).filter(User.user_id == user_id).first()
            if user and user.is_active:
                logger.info(f"[AUTH] JWT authentication successful for user: {user_id}")
                return user
    
    # Fallback to HTTP Basic Auth (for existing endpoints)
    if credentials:
        user = authenticate_user(db, credentials.username, credentials.password)
        if user:
            logger.info(f"[AUTH] Basic authentication successful for user: {credentials.username}")
            return user
    
    # Both methods failed
    logger.warning("[AUTH] Authentication failed - no valid credentials provided")
    raise HTTPException(
        status_code=401,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Basic"},
    )


async def get_current_user_optional(
    db: Session = Depends(get_db),
    credentials: Optional[HTTPBasicCredentials] = Depends(security),
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
):
    """
    Optional authentication dependency - returns user if authenticated, None if not
    Used for endpoints that can work with or without authentication
    """
    try:
        # Try JWT Bearer token first
        if bearer and bearer.credentials:
            token = bearer.credentials
            payload = decode_jwt_token(token)
            if payload and "user_id" in payload:
                user_id = payload["user_id"].lower().strip()
                user = db.query(User).filter(User.user_id == user_id).first()
                if user and user.is_active:
                    logger.info(f"[AUTH] Optional JWT authentication successful for user: {user_id}")
                    return user
        
        # Fallback to HTTP Basic Auth
        if credentials:
            user = authenticate_user(db, credentials.username, credentials.password)
            if user:
                logger.info(f"[AUTH] Optional Basic authentication successful for user: {credentials.username}")
                return user
    
    except Exception as e:
        logger.warning(f"[AUTH] Optional authentication failed: {e}")
    
    # No valid credentials - return None (no error)
    logger.info("[AUTH] No authentication provided - proceeding without user context")
    return None


@limiter.limit("5/minute")
async def register_user(request: Request, db: Session = Depends(get_db)):
    """Register new user endpoint - requires valid email"""
    try:
        import re
        
        body = await request.json()
        user_id = body.get("user_id")
        password = body.get("password")
        first_name = body.get("first_name", "").strip()
        last_name = body.get("last_name", "").strip()
        
        if not user_id or not password:
            raise HTTPException(status_code=400, detail="Email and password are required")
        
        if not first_name or not last_name:
            raise HTTPException(status_code=400, detail="First name and last name are required")
        
        # Validate email format
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, user_id):
            raise HTTPException(
                status_code=400,
                detail="Invalid email format. Please use a valid email address (e.g., user@example.com)"
            )
        
        # Normalize email to lowercase
        user_id = user_id.lower().strip()
        
        # Validate password strength (for NEW users only)
        if len(password) < 8:
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 8 characters long"
            )
        
        # Check password complexity
        has_upper = re.search(r'[A-Z]', password)
        has_lower = re.search(r'[a-z]', password)
        has_digit = re.search(r'\d', password)
        has_special = re.search(r'[!@#$%^&*(),.?":{}|<>]', password)
        
        if not all([has_upper, has_lower, has_digit, has_special]):
            raise HTTPException(
                status_code=400,
                detail="Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character (!@#$%^&*(),.?\":{}|<>)"
            )
        
        # Check if user exists
        existing_user = db.query(User).filter(User.user_id == user_id).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered. Please login or use a different email.")
        
        # Create user
        user = create_user(db, user_id, password, first_name, last_name)
        
        # Create empty resume template for new user
        from app.database import UserResumeTemplate
        empty_template = {
            "name": "",
            "contact": {},
            "summary": "",
            "skills": [],
            "experience": [],
            "education": [],
            "projects": [],
            "certifications": []
        }
        
        new_template = UserResumeTemplate(
            user_id=user.user_id,
            resume_data=empty_template
        )
        db.add(new_template)
        db.commit()
        
        logger.info(f"[REGISTER] Created empty template for user: {user_id}")
        
        return {
            "message": "User registered successfully",
            "user_id": user.user_id,
            "first_name": user.first_name,
            "last_name": user.last_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


async def login_user(
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """User login endpoint - supports both legacy usernames and email"""
    import re
    
    username = credentials.username
    password = credentials.password
    
    # Normalize to lowercase
    username = username.lower().strip()
    
    logger.info(f"[LOGIN ATTEMPT] User: {username}")
    
    # Check email format (for better UX guidance)
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    is_email_format = re.match(email_regex, username)
    
    if not is_email_format:
        # Allow legacy username login but warn in logs
        logger.info(f"[LOGIN] Legacy username format detected: {username}")
    

    # Check if user exists (works for both email and username)
    user = db.query(User).filter(User.user_id == username).first()
    if not user:
        logger.warning(f"[LOGIN FAILED] User not found: {username}")
        raise HTTPException(
            status_code=401,
            detail="User not found. Please register first."
        )

    # Verify password
    if not verify_password(password, user.password_hash):
        logger.warning(f"[LOGIN FAILED] Invalid password for user: {username}")
        raise HTTPException(
            status_code=401,
            detail="Invalid password. Please try again."
        )

    logger.info(f"[LOGIN SUCCESS] User: {username}")

    # Issue JWT token
    import jwt
    import os
    JWT_SECRET = os.getenv("JWT_SECRET", "resume_jwt_secret_2025")
    JWT_ALGORITHM = "HS256"
    token = jwt.encode({
        "user_id": user.user_id,
        "exp": int(datetime.utcnow().timestamp()) + 86400  # 24h expiry
    }, JWT_SECRET, algorithm=JWT_ALGORITHM)

    return {
        "message": "Login successful",
        "username": user.user_id,
        "user_id": user.user_id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "token": token
    }


@limiter.limit("3/minute")
async def reset_password(request: Request, db: Session = Depends(get_db)):
    """Reset password endpoint - supports both email and legacy username"""
    try:
        import re
        
        body = await request.json()
        username = body.get("username")
        new_password = body.get("new_password")
        
        if not username or not new_password:
            raise HTTPException(
                status_code=400,
                detail="Username/Email and new password are required"
            )
        
        # Normalize to lowercase
        username = username.lower().strip()
        
        # Check email format (for logging, but allow both)
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        is_email_format = re.match(email_regex, username)
        
        if not is_email_format:
            logger.info(f"[PASSWORD RESET] Legacy username format: {username}")
        
        # Password validation (8+ chars minimum for backward compatibility)
        if len(new_password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")
        
        # Check if user exists
        user = db.query(User).filter(User.user_id == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update password
        from app.database import hash_password
        user.password_hash = hash_password(new_password)
        db.commit()
        
        logger.info(f"[PASSWORD RESET] User: {username}")
        
        return {
            "message": "Password reset successful",
            "username": username
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Password reset failed: {str(e)}")


async def update_profile(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user profile (first_name and last_name)"""
    try:
        body = await request.json()
        first_name = body.get("first_name", "").strip()
        last_name = body.get("last_name", "").strip()
        
        if not first_name or not last_name:
            raise HTTPException(status_code=400, detail="First name and last name are required")
        
        # Update user profile
        user.first_name = first_name
        user.last_name = last_name
        db.commit()
        db.refresh(user)
        
        logger.info(f"[PROFILE UPDATE] User: {user.user_id} - Name: {first_name} {last_name}")
        
        return {
            "message": "Profile updated successfully",
            "user_id": user.user_id,
            "first_name": user.first_name,
            "last_name": user.last_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile update error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Profile update failed: {str(e)}")

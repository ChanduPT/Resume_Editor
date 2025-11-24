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
import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "resume_jwt_secret_2025")
JWT_ALGORITHM = "HS256"
bearer_scheme = HTTPBearer()

def decode_jwt_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception as e:
        logger.warning(f"[AUTH] JWT decode failed: {e}")
        return None

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
):
    """Dependency to get current authenticated user (JWT)"""
    token = credentials.credentials
    payload = decode_jwt_token(token)
    if not payload or "user_id" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user_id = payload["user_id"].lower().strip()
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


@limiter.limit("5/minute")
async def register_user(request: Request, db: Session = Depends(get_db)):
    """Register new user endpoint - requires valid email"""
    try:
        import re
        
        body = await request.json()
        user_id = body.get("user_id")
        password = body.get("password")
        
        if not user_id or not password:
            raise HTTPException(status_code=400, detail="Email and password are required")
        
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
        user = create_user(db, user_id, password)
        
        return {
            "message": "User registered successfully",
            "user_id": user.user_id
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

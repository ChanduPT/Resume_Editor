# app/auth.py
# Authentication endpoints and dependencies

from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
import logging

from app.database import get_db, User, authenticate_user, verify_password, create_user

logger = logging.getLogger(__name__)
security = HTTPBasic()
limiter = Limiter(key_func=get_remote_address)


async def get_current_user(
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Dependency to get current authenticated user"""
    user = authenticate_user(db, credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user


@limiter.limit("5/minute")
async def register_user(request: Request, db: Session = Depends(get_db)):
    """Register new user endpoint"""
    try:
        body = await request.json()
        user_id = body.get("user_id")
        password = body.get("password")
        
        if not user_id or not password:
            raise HTTPException(status_code=400, detail="user_id and password are required")
        
        # Validate password strength
        if len(password) < 8:
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 8 characters long"
            )
        
        # Check if user exists
        existing_user = db.query(User).filter(User.user_id == user_id).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="User already exists")
        
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
    """User login endpoint with specific error messages"""
    username = credentials.username
    password = credentials.password
    
    logger.info(f"[LOGIN ATTEMPT] User: {username}")
    
    # Check if user exists
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
    
    return {
        "message": "Login successful",
        "username": user.user_id,
        "user_id": user.user_id
    }


@limiter.limit("3/minute")
async def reset_password(request: Request, db: Session = Depends(get_db)):
    """Reset password endpoint"""
    try:
        body = await request.json()
        username = body.get("username")
        new_password = body.get("new_password")
        
        if not username or not new_password:
            raise HTTPException(status_code=400, detail="Username and new password are required")
        
        # Validate password strength
        if len(new_password) < 8:
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 8 characters long"
            )
        
        # Check if user exists
        user = db.query(User).filter(User.user_id == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update password
        from app.database import get_password_hash
        user.password_hash = get_password_hash(new_password)
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

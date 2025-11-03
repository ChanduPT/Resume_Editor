# app/database.py

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
import hashlib

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), unique=True, index=True)  # username/email
    password_hash = Column(String(255))  # hashed password
    
    # Usage tracking
    total_resumes_generated = Column(Integer, default=0)
    active_jobs_count = Column(Integer, default=0)  # Current processing jobs
    
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

class UserResumeTemplate(Base):
    __tablename__ = "user_resume_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), unique=True, index=True)  # One template per user
    
    # Resume data (name, contact, summary, skills, experience, education, projects, certifications)
    resume_data = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ResumeJob(Base):
    __tablename__ = "resume_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), index=True)  # Foreign key to users.user_id
    request_id = Column(String(255), unique=True, index=True)
    
    # Job details
    company_name = Column(String(255), index=True)
    job_title = Column(String(255))
    mode = Column(String(50))  # "complete_jd" or "resume_jd"
    
    # Input data
    jd_text = Column(Text)
    resume_input_json = Column(JSON)
    
    # Output data
    final_resume_json = Column(JSON)
    
    # Job status
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    progress = Column(Integer, default=0)  # 0-100
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

# Database connection
def get_database_url():
    """Get database URL - supports PostgreSQL and SQLite"""
    db_url = os.getenv("DATABASE_URL")
    
    if db_url:
        # Render/Heroku use postgres:// but SQLAlchemy needs postgresql://
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return db_url
    else:
        # Local development with SQLite
        return "sqlite:///./resume_editor.db"

engine = create_engine(
    get_database_url(), 
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if "sqlite" in get_database_url() else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)

# Auth helpers
def hash_password(password: str) -> str:
    """Hash password with salt"""
    salt = os.getenv("PASSWORD_SALT", "resume_editor_salt_2025").encode('utf-8')
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000).hex()

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash"""
    return hash_password(password) == password_hash

def create_user(db, user_id: str, password: str) -> User:
    """Create new user"""
    password_hash = hash_password(password)
    user = User(user_id=user_id, password_hash=password_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def authenticate_user(db, user_id: str, password: str) -> User:
    """Authenticate user"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if user and user.is_active and verify_password(password, user.password_hash):
        user.last_login = datetime.utcnow()
        db.commit()
        return user
    return None

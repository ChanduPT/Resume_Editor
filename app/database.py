# app/database.py

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON, Boolean, Index, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import os
import hashlib
import json

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

class JobSearchCache(Base):
    """
    Cache for job search results
    Stores scraped job postings with TTL to reduce redundant scraping
    """
    __tablename__ = "job_search_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Cache key components
    search_key = Column(String(255), unique=True, index=True)  # MD5 hash of search params
    job_title = Column(String(255), index=True)  # For analytics
    location = Column(String(255))
    sources = Column(String(255))  # Comma-separated list
    
    # Cached data
    jobs_json = Column(JSON)  # Array of job objects
    total_results = Column(Integer)
    
    # Cache metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime, index=True)  # TTL expiration
    hit_count = Column(Integer, default=0)  # Track cache hits for analytics
    last_accessed = Column(DateTime, default=datetime.utcnow)
    
    # Composite index for efficient queries
    __table_args__ = (
        Index('idx_job_title_location', 'job_title', 'location'),
        Index('idx_expires_at_search_key', 'expires_at', 'search_key'),
    )

class JobPosting(Base):
    """
    Individual job posting storage
    Normalized storage for deduplication and better querying
    """
    __tablename__ = "job_postings"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Job identifiers
    job_url = Column(String(512), unique=True, index=True)  # URL is unique identifier
    job_url_hash = Column(String(64), unique=True, index=True)  # MD5 hash for faster lookup
    
    # Job details
    title = Column(String(512))
    company = Column(String(255), index=True)
    location = Column(String(255))
    source = Column(String(50))  # workday, greenhouse, lever, linkedin
    snippet = Column(Text)
    
    # Full description (cached after scraping)
    full_description = Column(Text, nullable=True)
    description_scraped_at = Column(DateTime, nullable=True)
    
    # Metadata
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    view_count = Column(Integer, default=0)  # Track popularity
    
    # Composite index for efficient searches
    __table_args__ = (
        Index('idx_company_title', 'company', 'title'),
        Index('idx_source_company', 'source', 'company'),
    )

class ResumeJob(Base):
    __tablename__ = "resume_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), index=True)  # Foreign key to users.user_id
    request_id = Column(String(255), unique=True, index=True)
    
    # Job details
    company_name = Column(String(255), index=True)
    job_title = Column(String(255))
    mode = Column(String(50))  # "complete_jd" or "resume_jd"
    format = Column(String(50), default="classic")  # "classic" or "modern"
    
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

# Job search cache helpers
def generate_cache_key(job_title: str, location: str, date_posted: str, sources: list) -> str:
    """
    Generate MD5 hash cache key from search parameters
    Ensures consistent caching for identical searches
    """
    # Normalize parameters
    job_title = job_title.lower().strip()
    location = location.lower().strip()
    date_posted = date_posted.lower().strip()
    sources_str = ",".join(sorted(sources))  # Sort for consistency
    
    # Create hash
    key_string = f"{job_title}|{location}|{date_posted}|{sources_str}"
    return hashlib.md5(key_string.encode('utf-8')).hexdigest()

def get_cached_job_search(db, cache_key: str) -> dict:
    """
    Retrieve cached job search results
    Returns None if cache miss or expired
    """
    cache_entry = db.query(JobSearchCache).filter(
        JobSearchCache.search_key == cache_key
    ).first()
    
    if not cache_entry:
        return None
    
    # Check expiration
    if cache_entry.expires_at < datetime.utcnow():
        # Cache expired - delete and return None
        db.delete(cache_entry)
        db.commit()
        return None
    
    # Update access metadata
    cache_entry.hit_count += 1
    cache_entry.last_accessed = datetime.utcnow()
    db.commit()
    
    return {
        "jobs": cache_entry.jobs_json,
        "total_results": cache_entry.total_results,
        "cached_at": cache_entry.created_at.isoformat(),
        "expires_at": cache_entry.expires_at.isoformat(),
        "hit_count": cache_entry.hit_count
    }

def store_job_search_cache(db, cache_key: str, job_title: str, location: str, 
                           sources: list, jobs: list, ttl_hours: int = 24) -> JobSearchCache:
    """
    Store job search results in cache with TTL
    Default TTL: 24 hours
    """
    # Check if cache entry already exists
    existing = db.query(JobSearchCache).filter(
        JobSearchCache.search_key == cache_key
    ).first()
    
    expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
    
    if existing:
        # Update existing cache
        existing.jobs_json = jobs
        existing.total_results = len(jobs)
        existing.created_at = datetime.utcnow()
        existing.expires_at = expires_at
        cache_entry = existing
    else:
        # Create new cache entry
        cache_entry = JobSearchCache(
            search_key=cache_key,
            job_title=job_title,
            location=location,
            sources=",".join(sources),
            jobs_json=jobs,
            total_results=len(jobs),
            expires_at=expires_at
        )
        db.add(cache_entry)
    
    db.commit()
    db.refresh(cache_entry)
    return cache_entry

def store_job_posting(db, job_url: str, title: str, company: str, location: str, 
                     source: str, snippet: str, full_description: str = None) -> JobPosting:
    """
    Store or update individual job posting
    Uses URL as unique identifier
    """
    # Generate URL hash for faster lookups
    url_hash = hashlib.md5(job_url.encode('utf-8')).hexdigest()
    
    # Check if job already exists
    existing = db.query(JobPosting).filter(
        JobPosting.job_url_hash == url_hash
    ).first()
    
    if existing:
        # Update last_seen and metadata
        existing.last_seen = datetime.utcnow()
        existing.view_count += 1
        
        # Update description if provided
        if full_description:
            existing.full_description = full_description
            existing.description_scraped_at = datetime.utcnow()
        
        job = existing
    else:
        # Create new job posting
        job = JobPosting(
            job_url=job_url,
            job_url_hash=url_hash,
            title=title,
            company=company,
            location=location,
            source=source,
            snippet=snippet,
            full_description=full_description,
            description_scraped_at=datetime.utcnow() if full_description else None
        )
        db.add(job)
    
    db.commit()
    db.refresh(job)
    return job

def get_job_description(db, job_url: str) -> str:
    """
    Get cached full job description by URL
    Returns None if not cached
    """
    url_hash = hashlib.md5(job_url.encode('utf-8')).hexdigest()
    job = db.query(JobPosting).filter(
        JobPosting.job_url_hash == url_hash
    ).first()
    
    if job and job.full_description:
        return job.full_description
    return None

def cleanup_expired_cache(db):
    """
    Remove expired cache entries
    Should be called periodically (e.g., daily cron job)
    """
    expired_count = db.query(JobSearchCache).filter(
        JobSearchCache.expires_at < datetime.utcnow()
    ).delete()
    
    db.commit()
    return expired_count

def get_cache_stats(db) -> dict:
    """
    Get cache performance statistics
    Useful for monitoring and optimization
    """
    total_entries = db.query(JobSearchCache).count()
    expired_entries = db.query(JobSearchCache).filter(
        JobSearchCache.expires_at < datetime.utcnow()
    ).count()
    
    # Most popular searches (by hit count)
    popular_searches = db.query(
        JobSearchCache.job_title, 
        JobSearchCache.location, 
        JobSearchCache.hit_count
    ).order_by(JobSearchCache.hit_count.desc()).limit(10).all()
    
    # Total hits
    total_hits = db.query(JobSearchCache).with_entities(
        func.sum(JobSearchCache.hit_count)
    ).scalar() or 0
    
    return {
        "total_cache_entries": total_entries,
        "expired_entries": expired_entries,
        "active_entries": total_entries - expired_entries,
        "total_cache_hits": total_hits,
        "popular_searches": [
            {"job_title": s[0], "location": s[1], "hits": s[2]} 
            for s in popular_searches
        ]
    }

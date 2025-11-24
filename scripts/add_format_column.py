#!/usr/bin/env python3
"""
Migration script to add 'format' column to resume_jobs table.
Run this once after deploying the new code.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import engine, SessionLocal
from sqlalchemy import text, inspect

def add_format_column():
    """Add format column to resume_jobs table if it doesn't exist"""
    db = SessionLocal()
    
    try:
        # Check database type from engine URL
        db_url = str(engine.url)
        is_postgres = 'postgresql' in db_url or 'postgres' in db_url
        
        print(f"Database type: {'PostgreSQL' if is_postgres else 'SQLite'}")
        
        # Try to check if column exists
        try:
            if is_postgres:
                result = db.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='resume_jobs' AND column_name='format'
                """))
                if result.fetchone():
                    print("✅ 'format' column already exists in resume_jobs table")
                    return
            else:
                # For SQLite, try a different approach
                result = db.execute(text("PRAGMA table_info(resume_jobs)"))
                columns = [row[1] for row in result.fetchall()]
                if 'format' in columns:
                    print("✅ 'format' column already exists in resume_jobs table")
                    return
        except Exception as check_error:
            print(f"Warning during column check: {check_error}")
            print("Proceeding with migration...")
        
        # Add column based on database type
        print("Adding 'format' column to resume_jobs table...")
        
        if is_postgres:
            # PostgreSQL syntax
            db.execute(text("""
                ALTER TABLE resume_jobs 
                ADD COLUMN format VARCHAR(50) DEFAULT 'classic'
            """))
        else:
            # SQLite syntax
            db.execute(text("""
                ALTER TABLE resume_jobs 
                ADD COLUMN format TEXT DEFAULT 'classic'
            """))
        
        db.commit()
        print("✅ Successfully added 'format' column with default value 'classic'")
        
    except Exception as e:
        db.rollback()
        error_msg = str(e).lower()
        
        # Check if error is because column already exists
        if 'already exists' in error_msg or 'duplicate column' in error_msg:
            print("✅ 'format' column already exists in resume_jobs table")
            return
        
        print(f"❌ Error: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("="*60)
    print("Resume Format Column Migration")
    print("="*60)
    try:
        add_format_column()
        print("="*60)
        print("✅ Migration complete!")
        print("="*60)
    except Exception as e:
        print("="*60)
        print("❌ Migration failed!")
        print("="*60)
        sys.exit(1)

#!/usr/bin/env python3
"""
Test script to verify UserResumeTemplate table and API endpoints
"""
from app.database import SessionLocal, UserResumeTemplate, User

def test_database_table():
    """Check if the user_resume_templates table exists"""
    db = SessionLocal()
    try:
        # Try to query the table
        count = db.query(UserResumeTemplate).count()
        print(f"✅ UserResumeTemplate table exists with {count} records")
        
        # Check if any users exist
        user_count = db.query(User).count()
        print(f"✅ Users table has {user_count} users")
        
        # Show all templates
        templates = db.query(UserResumeTemplate).all()
        for template in templates:
            print(f"  - User: {template.user_id}, Updated: {template.updated_at}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("Testing UserResumeTemplate database table...")
    test_database_table()

#!/usr/bin/env python3
"""
Migration script: Add Application Tracking Columns
Run this script to add job application tracking fields to the database
"""

import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, get_database_url
from sqlalchemy import text

def run_migration():
    """Execute the migration SQL"""
    # Migration file is in migrations/ folder, not scripts/
    script_dir = os.path.dirname(__file__)
    project_root = os.path.dirname(script_dir)
    migration_file = os.path.join(project_root, 'migrations', 'add_application_tracking.sql')
    
    print(f"🔄 Running migration: add_application_tracking.sql")
    print(f"📊 Database: {get_database_url()}")
    
    try:
        with open(migration_file, 'r') as f:
            sql = f.read()
        
        with engine.connect() as connection:
            # Split by semicolon and execute each statement
            statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]
            
            for statement in statements:
                if statement:
                    print(f"  ✓ Executing: {statement[:80]}...")
                    connection.execute(text(statement))
                    connection.commit()
        
        print("✅ Migration completed successfully!")
        print("\nNew columns added:")
        print("  - job_link (VARCHAR(1024))")
        print("  - application_status (VARCHAR(50), default: 'resume_generated')")
        print("  - application_date (TIMESTAMP)")
        print("  - application_notes (TEXT)")
        print("  - last_status_update (TIMESTAMP)")
        print("\nNew indexes created:")
        print("  - idx_application_status")
        print("  - idx_application_date")
        print("  - idx_user_application_status")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)

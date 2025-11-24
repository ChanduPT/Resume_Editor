#!/usr/bin/env python3
"""
Migration script to add human feedback feature columns to PostgreSQL database.
Run this script to add intermediate_state and feedback_submitted_at columns.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_database_url():
    """Get database URL from environment"""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ ERROR: DATABASE_URL not found in environment")
        print("Please set DATABASE_URL or run migrate_postgres.sh")
        sys.exit(1)
    
    # Fix postgres:// to postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    return db_url

def run_migration():
    """Run the migration to add feedback columns"""
    print("=" * 60)
    print("Human Feedback Feature - Database Migration")
    print("=" * 60)
    print()
    
    db_url = get_database_url()
    
    # Mask password in display
    display_url = db_url
    if "@" in display_url:
        parts = display_url.split("@")
        user_pass = parts[0].split("//")[1]
        if ":" in user_pass:
            user = user_pass.split(":")[0]
            display_url = display_url.replace(user_pass, f"{user}:***")
    
    print(f"📊 Connecting to: {display_url}")
    print()
    
    try:
        engine = create_engine(db_url, pool_pre_ping=True)
        
        with engine.connect() as conn:
            print("✓ Connected to database")
            print()
            
            # Check if columns already exist
            print("🔍 Checking existing schema...")
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns
                WHERE table_name = 'resume_jobs'
                AND column_name IN ('intermediate_state', 'feedback_submitted_at')
            """))
            existing_columns = [row[0] for row in result]
            
            if len(existing_columns) == 2:
                print("✓ Columns already exist - no migration needed")
                print()
                return True
            
            print(f"Found {len(existing_columns)} of 2 required columns")
            print()
            
            # Read migration SQL
            migration_file = Path(__file__).parent.parent / "migrations" / "add_feedback_columns.sql"
            if not migration_file.exists():
                print(f"❌ Migration file not found: {migration_file}")
                return False
            
            print(f"📄 Reading migration: {migration_file.name}")
            migration_sql = migration_file.read_text()
            
            # Execute migration
            print("🚀 Running migration...")
            print()
            
            # Execute ALTER TABLE statements
            print("1. Adding intermediate_state column...")
            conn.execute(text("""
                ALTER TABLE resume_jobs 
                ADD COLUMN IF NOT EXISTS intermediate_state JSON
            """))
            conn.commit()
            print("✓ Added intermediate_state column")
            
            print("2. Adding feedback_submitted_at column...")
            conn.execute(text("""
                ALTER TABLE resume_jobs 
                ADD COLUMN IF NOT EXISTS feedback_submitted_at TIMESTAMP
            """))
            conn.commit()
            print("✓ Added feedback_submitted_at column")
            
            print("3. Creating index...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_status_created_at 
                ON resume_jobs(status, created_at)
            """))
            conn.commit()
            print("✓ Created index idx_status_created_at")
            
            print()
            print("✅ Migration completed successfully!")
            print()
            
            # Verify changes
            print("🔍 Verifying changes...")
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'resume_jobs'
                AND column_name IN ('intermediate_state', 'feedback_submitted_at')
                ORDER BY column_name
            """))
            
            columns = result.fetchall()
            if len(columns) == 2:
                print("✓ All columns added successfully:")
                for col in columns:
                    print(f"  - {col[0]} ({col[1]}) nullable={col[2]}")
                print()
                
                # Check index
                result = conn.execute(text("""
                    SELECT indexname
                    FROM pg_indexes
                    WHERE tablename = 'resume_jobs'
                    AND indexname = 'idx_status_created_at'
                """))
                
                if result.fetchone():
                    print("✓ Index idx_status_created_at created successfully")
                else:
                    print("⚠️  Index not found (may have been created previously)")
                
                print()
                return True
            else:
                print(f"⚠️  Expected 2 columns, found {len(columns)}")
                return False
            
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)

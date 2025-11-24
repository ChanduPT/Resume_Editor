#!/usr/bin/env python3
"""
Database migration script for Render deployment
Adds missing columns to resume_jobs table
"""

import os
import sys
from sqlalchemy import create_engine, text

def get_database_url():
    """Get database URL from environment"""
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("ERROR: DATABASE_URL environment variable is not set")
        sys.exit(1)
    
    # Render uses postgres:// but SQLAlchemy needs postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    return db_url

def run_migration(engine):
    """Run database migrations"""
    
    with engine.connect() as conn:
        print("Starting database migration...")
        
        # Start transaction
        trans = conn.begin()
        
        try:
            # Check if format column exists
            print("\n1. Checking for 'format' column...")
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'resume_jobs' 
                AND column_name = 'format'
            """))
            
            if result.fetchone() is None:
                print("   'format' column not found. Adding...")
                conn.execute(text("""
                    ALTER TABLE resume_jobs 
                    ADD COLUMN format VARCHAR(50) DEFAULT 'classic'
                """))
                print("   ✓ Added 'format' column")
            else:
                print("   ✓ 'format' column already exists")
            
            # Check if intermediate_state column exists
            print("\n2. Checking for 'intermediate_state' column...")
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'resume_jobs' 
                AND column_name = 'intermediate_state'
            """))
            
            if result.fetchone() is None:
                print("   'intermediate_state' column not found. Adding...")
                conn.execute(text("""
                    ALTER TABLE resume_jobs 
                    ADD COLUMN intermediate_state JSON
                """))
                print("   ✓ Added 'intermediate_state' column")
            else:
                print("   ✓ 'intermediate_state' column already exists")
            
            # Check if feedback_submitted_at column exists
            print("\n3. Checking for 'feedback_submitted_at' column...")
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'resume_jobs' 
                AND column_name = 'feedback_submitted_at'
            """))
            
            if result.fetchone() is None:
                print("   'feedback_submitted_at' column not found. Adding...")
                conn.execute(text("""
                    ALTER TABLE resume_jobs 
                    ADD COLUMN feedback_submitted_at TIMESTAMP
                """))
                print("   ✓ Added 'feedback_submitted_at' column")
            else:
                print("   ✓ 'feedback_submitted_at' column already exists")
            
            # Check if index exists
            print("\n4. Checking for 'idx_status_created_at' index...")
            result = conn.execute(text("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'resume_jobs' 
                AND indexname = 'idx_status_created_at'
            """))
            
            if result.fetchone() is None:
                print("   Index not found. Creating...")
                conn.execute(text("""
                    CREATE INDEX idx_status_created_at 
                    ON resume_jobs(status, created_at)
                """))
                print("   ✓ Created index 'idx_status_created_at'")
            else:
                print("   ✓ Index 'idx_status_created_at' already exists")
            
            # Commit transaction
            trans.commit()
            print("\n✅ All migrations completed successfully!")
            
            # Show final schema
            print("\n" + "="*60)
            print("Current resume_jobs table schema:")
            print("="*60)
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'resume_jobs'
                ORDER BY ordinal_position
            """))
            
            print(f"{'Column Name':<30} {'Type':<20} {'Nullable':<10} {'Default'}")
            print("-" * 90)
            for row in result:
                default = str(row[3])[:30] if row[3] else "NULL"
                print(f"{row[0]:<30} {row[1]:<20} {row[2]:<10} {default}")
            
        except Exception as e:
            trans.rollback()
            print(f"\n❌ Migration failed: {e}")
            sys.exit(1)

def main():
    """Main function"""
    print("="*60)
    print("Resume Editor - Database Migration")
    print("="*60)
    
    db_url = get_database_url()
    print(f"\nConnecting to database...")
    
    try:
        engine = create_engine(db_url, pool_pre_ping=True)
        run_migration(engine)
        engine.dispose()
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

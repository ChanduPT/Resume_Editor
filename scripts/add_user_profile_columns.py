#!/usr/bin/env python3
"""
Migration script to add first_name and last_name columns to users table
Run this after updating the codebase to add user profile support
This script is safe to run multiple times - it checks if columns exist first
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text, inspect
from app.database import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Add first_name and last_name columns to users table (PostgreSQL safe)"""
    try:
        logger.info("Connecting to PostgreSQL database...")
        
        # Check if tables exist
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if 'users' not in tables:
            logger.error("❌ Users table does not exist!")
            logger.info("Please start the application first to create tables, then run this migration.")
            sys.exit(1)
        
        # Table exists, check if columns exist
        columns = [col['name'] for col in inspector.get_columns('users')]
        logger.info(f"Current columns in users table: {columns}")
        
        if 'first_name' in columns and 'last_name' in columns:
            logger.info("✅ Columns first_name and last_name already exist. No migration needed!")
            return
        
        # Need to add columns (safe operation - existing data preserved)
        with engine.connect() as conn:
            trans = conn.begin()
            
            try:
                if 'first_name' not in columns:
                    logger.info("Adding first_name column to users table...")
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR(100)"))
                    logger.info("✅ Added first_name column")
                
                if 'last_name' not in columns:
                    logger.info("Adding last_name column to users table...")
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR(100)"))
                    logger.info("✅ Added last_name column")
                
                trans.commit()
                logger.info("✅ Migration completed successfully!")
                logger.info("📝 Existing user data is preserved - new columns are nullable")
                logger.info("📝 Existing users can update their names via the Profile modal")
                
            except Exception as e:
                trans.rollback()
                logger.error(f"❌ Migration failed: {e}")
                raise
                
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    logger.info("Starting migration: Add user profile fields")
    logger.info("=" * 60)
    run_migration()
    logger.info("=" * 60)
    logger.info("Migration complete. You can now use the profile features!")

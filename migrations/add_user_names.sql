-- Migration: Add first_name and last_name to users table
-- Date: 2025-12-07
-- Purpose: Support user profile information for personalized resume downloads

-- Add first_name column
ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR(100);

-- Add last_name column
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR(100);

-- Optional: Add index for faster queries (if needed for search functionality later)
-- CREATE INDEX IF NOT EXISTS idx_users_first_name ON users(first_name);
-- CREATE INDEX IF NOT EXISTS idx_users_last_name ON users(last_name);

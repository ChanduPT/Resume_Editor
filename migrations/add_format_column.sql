-- Migration: Add format column to resume_jobs
-- Date: 2025-11-24
-- Description: Adds format column to support classic/modern resume styles

-- Add format column with default value
ALTER TABLE resume_jobs 
ADD COLUMN IF NOT EXISTS format VARCHAR(50) DEFAULT 'classic';

-- Update any existing rows to have the default format
UPDATE resume_jobs 
SET format = 'classic' 
WHERE format IS NULL;

-- Verify the changes
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'resume_jobs'
AND column_name = 'format';

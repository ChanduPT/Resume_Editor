-- Migration: Add Human Feedback Feature Columns
-- Date: 2025-11-23
-- Description: Adds columns to support two-phase resume generation with human feedback

-- Add intermediate_state column to store extracted keywords
ALTER TABLE resume_jobs 
ADD COLUMN IF NOT EXISTS intermediate_state JSON;

-- Add feedback_submitted_at column to track when user provides feedback
ALTER TABLE resume_jobs 
ADD COLUMN IF NOT EXISTS feedback_submitted_at TIMESTAMP;

-- Create index for efficient cleanup queries
CREATE INDEX IF NOT EXISTS idx_status_created_at 
ON resume_jobs(status, created_at);

-- Update any existing 'pending' or 'processing' jobs to ensure they work with new schema
-- (This is a safety measure for existing data)
COMMENT ON COLUMN resume_jobs.intermediate_state IS 'Stores extracted JD keywords for user review in awaiting_feedback state';
COMMENT ON COLUMN resume_jobs.feedback_submitted_at IS 'Timestamp when user submitted feedback for Phase 2 generation';

-- Verify the changes
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'resume_jobs'
AND column_name IN ('intermediate_state', 'feedback_submitted_at')
ORDER BY column_name;

-- Verify the index
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'resume_jobs'
AND indexname = 'idx_status_created_at';

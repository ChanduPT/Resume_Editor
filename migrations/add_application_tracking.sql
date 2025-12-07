-- Migration: Add Application Tracking Columns
-- Date: 2025-12-06
-- Description: Add job application tracking fields to resume_jobs table

-- Add new columns for application tracking
ALTER TABLE resume_jobs 
ADD COLUMN IF NOT EXISTS job_link VARCHAR(1024),
ADD COLUMN IF NOT EXISTS application_status VARCHAR(50) DEFAULT 'resume_generated',
ADD COLUMN IF NOT EXISTS application_date TIMESTAMP,
ADD COLUMN IF NOT EXISTS application_notes TEXT,
ADD COLUMN IF NOT EXISTS last_status_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Create index for efficient filtering by application status
CREATE INDEX IF NOT EXISTS idx_application_status ON resume_jobs(application_status);

-- Create index for application date queries
CREATE INDEX IF NOT EXISTS idx_application_date ON resume_jobs(application_date);

-- Create composite index for user + status queries
CREATE INDEX IF NOT EXISTS idx_user_application_status ON resume_jobs(user_id, application_status);

-- Add comment to document allowed status values
COMMENT ON COLUMN resume_jobs.application_status IS 'Allowed values: resume_generated, applied, rejected, screening, interview, offer';

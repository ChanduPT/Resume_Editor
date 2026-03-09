-- Add missing metadata column to user_feedback table
-- Using feedback_metadata as the actual column name for clarity

ALTER TABLE user_feedback ADD COLUMN IF NOT EXISTS feedback_metadata JSONB DEFAULT '{}'::jsonb;

-- Add index for better query performance
CREATE INDEX IF NOT EXISTS idx_user_feedback_metadata ON user_feedback USING gin(feedback_metadata);

COMMENT ON COLUMN user_feedback.feedback_metadata IS 'Additional context like category, affected feature, etc.';

SELECT 'Successfully added feedback_metadata column to user_feedback table' as status;

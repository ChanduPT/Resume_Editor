-- Fix chatbot table columns to match SQLAlchemy models
-- Changes started_at/ended_at to created_at/updated_at for consistency

-- Fix chat_sessions table
ALTER TABLE chat_sessions RENAME COLUMN started_at TO created_at;
ALTER TABLE chat_sessions DROP COLUMN IF EXISTS ended_at;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- Update the index to use the new column name
DROP INDEX IF EXISTS idx_chat_sessions_started;
CREATE INDEX idx_chat_sessions_created ON chat_sessions(created_at DESC);

-- Fix chat_messages table (rename timestamp to created_at)
ALTER TABLE chat_messages RENAME COLUMN timestamp TO created_at;
DROP INDEX IF EXISTS idx_chat_messages_timestamp;
CREATE INDEX idx_chat_messages_created ON chat_messages(created_at);

-- Add update trigger for chat_sessions.updated_at
CREATE OR REPLACE FUNCTION update_chat_sessions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_chat_sessions_updated_at ON chat_sessions;
CREATE TRIGGER trigger_update_chat_sessions_updated_at
    BEFORE UPDATE ON chat_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_chat_sessions_updated_at();

COMMENT ON TABLE chat_sessions IS 'Chat sessions for Help, Interview, Chat, and Feedback modes';
COMMENT ON TABLE chat_messages IS 'Individual messages within a chat session';

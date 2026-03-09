-- AI Chatbot Feature Migration
-- Creates tables for chat sessions, interviews, feedback, and rate limiting

-- Chat Sessions Table
-- Stores all chat conversations (help, interview, general chat, feedback)
CREATE TABLE IF NOT EXISTS chat_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_type VARCHAR(20) NOT NULL CHECK (session_type IN ('help', 'interview', 'chat', 'feedback')),
    job_title VARCHAR(200),
    job_description TEXT,
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb,
    CONSTRAINT valid_session_type CHECK (session_type IN ('help', 'interview', 'chat', 'feedback'))
);

CREATE INDEX idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX idx_chat_sessions_type ON chat_sessions(session_type);
CREATE INDEX idx_chat_sessions_started ON chat_sessions(started_at DESC);

-- Chat Messages Table
-- Stores individual messages within a chat session
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),
    CONSTRAINT valid_role CHECK (role IN ('user', 'assistant', 'system'))
);

CREATE INDEX idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX idx_chat_messages_timestamp ON chat_messages(timestamp);

-- Interview Sessions Table
-- Stores completed interviews with scoring and feedback
CREATE TABLE IF NOT EXISTS interview_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chat_session_id INTEGER REFERENCES chat_sessions(id) ON DELETE SET NULL,
    job_title VARCHAR(200) NOT NULL,
    job_description TEXT NOT NULL,
    questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    answers JSONB NOT NULL DEFAULT '[]'::jsonb,
    overall_score FLOAT CHECK (overall_score >= 0 AND overall_score <= 10),
    technical_score FLOAT,
    communication_score FLOAT,
    problem_solving_score FLOAT,
    behavioral_score FLOAT,
    detailed_feedback TEXT,
    strengths TEXT[],
    improvements TEXT[],
    share_token VARCHAR(100) UNIQUE,
    is_public BOOLEAN DEFAULT FALSE,
    duration_minutes INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_interview_sessions_user ON interview_sessions(user_id);
CREATE INDEX idx_interview_sessions_share_token ON interview_sessions(share_token);
CREATE INDEX idx_interview_sessions_created ON interview_sessions(created_at DESC);

-- Interview Usage Tracking (Rate Limiting)
-- Tracks daily interview session count per user
CREATE TABLE IF NOT EXISTS interview_usage (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_date DATE NOT NULL DEFAULT CURRENT_DATE,
    session_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE(user_id, session_date)
);

CREATE INDEX idx_interview_usage_user_date ON interview_usage(user_id, session_date);

-- User Feedback Table
-- Stores bug reports, feature requests, and general feedback
CREATE TABLE IF NOT EXISTS user_feedback (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    feedback_type VARCHAR(20) NOT NULL CHECK (feedback_type IN ('bug', 'feature', 'general')),
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    page_url VARCHAR(500),
    browser_info JSONB,
    status VARCHAR(20) DEFAULT 'open' CHECK (status IN ('open', 'reviewing', 'resolved', 'closed')),
    priority VARCHAR(20) DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    admin_notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT valid_feedback_type CHECK (feedback_type IN ('bug', 'feature', 'general')),
    CONSTRAINT valid_status CHECK (status IN ('open', 'reviewing', 'resolved', 'closed')),
    CONSTRAINT valid_priority CHECK (priority IN ('low', 'medium', 'high', 'critical'))
);

CREATE INDEX idx_user_feedback_user ON user_feedback(user_id);
CREATE INDEX idx_user_feedback_type ON user_feedback(feedback_type);
CREATE INDEX idx_user_feedback_status ON user_feedback(status);
CREATE INDEX idx_user_feedback_created ON user_feedback(created_at DESC);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for user_feedback updated_at
CREATE TRIGGER update_user_feedback_updated_at BEFORE UPDATE ON user_feedback
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE chat_sessions IS 'Stores all chatbot conversation sessions';
COMMENT ON TABLE chat_messages IS 'Individual messages within chat sessions';
COMMENT ON TABLE interview_sessions IS 'Completed interview sessions with scores and reports';
COMMENT ON TABLE interview_usage IS 'Daily rate limiting for interview sessions';
COMMENT ON TABLE user_feedback IS 'User-submitted bugs, features, and feedback';

"""
Configuration for AI Chatbot feature
"""

# Rate Limiting
MAX_INTERVIEWS_PER_DAY = 2
MAX_CHAT_MESSAGES_PER_HOUR = 50

# Interview Settings
QUESTIONS_PER_INTERVIEW = 7
MAX_QUESTIONS_PER_INTERVIEW = 7  # Alias for backward compatibility
MAX_FOLLOW_UPS_PER_QUESTION = 2
INTERVIEW_TIME_LIMIT_MINUTES = 45

# Question Distribution
TECHNICAL_QUESTIONS = 3
BEHAVIORAL_QUESTIONS = 2
SITUATIONAL_QUESTIONS = 2

QUESTION_DISTRIBUTION = {
    "technical": TECHNICAL_QUESTIONS,
    "behavioral": BEHAVIORAL_QUESTIONS,
    "situational": SITUATIONAL_QUESTIONS
}

# Scoring Weights
SCORING_WEIGHTS = {
    "technical": 40,  # 40%
    "communication": 30,  # 30%
    "problem_solving": 20,  # 20%
    "real_world": 10  # 10%
}

# RAG Settings
RAG_CHUNK_SIZE = 500
RAG_CHUNK_OVERLAP = 50
RAG_TOP_K_RESULTS = 3
RAG_SIMILARITY_THRESHOLD = 0.7

# AI Model Settings
CHATBOT_TEMPERATURE = 0.7
INTERVIEW_TEMPERATURE = 0.3  # More deterministic for interviews
MAX_TOKENS = 1000

# Session Settings
SESSION_TIMEOUT_MINUTES = 60
MAX_MESSAGE_LENGTH = 5000

# Feedback Settings
FEEDBACK_PRIORITY_AUTO_ASSIGN = True  # Auto-assign priority based on keywords
HIGH_PRIORITY_KEYWORDS = [
    "crash", "broken", "error", "urgent", "critical", 
    "cannot", "won't work", "lost data", "security"
]

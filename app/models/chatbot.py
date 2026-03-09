"""
Pydantic models for AI Chatbot feature
Defines data structures for chat sessions, interviews, and feedback
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# Enums for type safety
class SessionType(str, Enum):
    HELP = "help"
    INTERVIEW = "interview"
    CHAT = "chat"
    FEEDBACK = "feedback"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class FeedbackType(str, Enum):
    BUG = "bug"
    FEATURE = "feature"
    GENERAL = "general"


class FeedbackStatus(str, Enum):
    OPEN = "open"
    REVIEWING = "reviewing"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ===== Chat Session Models =====

class ChatSessionCreate(BaseModel):
    """Request to start a new chat session"""
    session_type: SessionType
    job_title: Optional[str] = None
    job_description: Optional[str] = None


class ChatMessageCreate(BaseModel):
    """Request to send a message in a session"""
    content: str = Field(..., min_length=1, max_length=5000)


class ChatMessage(BaseModel):
    """Chat message response"""
    id: int
    session_id: int
    role: MessageRole
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSession(BaseModel):
    """Chat session response"""
    id: int
    user_id: int
    session_type: SessionType
    job_title: Optional[str] = None
    job_description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatHistoryResponse(BaseModel):
    """Response containing session and its messages"""
    session: ChatSession
    messages: List[ChatMessage]


# ===== Interview Models =====

class InterviewStartRequest(BaseModel):
    """Request to start an interview session"""
    job_title: str = Field(..., min_length=1, max_length=200)
    job_description: str = Field(..., min_length=10)


class InterviewQuestion(BaseModel):
    """Single interview question"""
    id: int
    question: str
    question_type: str  # 'technical', 'behavioral', 'situational'
    order: int
    is_follow_up: bool = False
    parent_question_id: Optional[int] = None


class InterviewAnswerRequest(BaseModel):
    """User's answer to an interview question"""
    question_id: int
    answer: str = Field(..., min_length=1)


class QuestionEvaluation(BaseModel):
    """Evaluation of a single answer"""
    score: float = Field(..., ge=0, le=10)
    feedback: str
    strengths: List[str] = []
    improvements: List[str] = []


class InterviewAnswerResponse(BaseModel):
    """Response after submitting an answer"""
    evaluation: QuestionEvaluation
    has_follow_up: bool
    follow_up_question: Optional[InterviewQuestion] = None
    next_question: Optional[InterviewQuestion] = None
    questions_remaining: int
    is_complete: bool = False


class CategoryScore(BaseModel):
    """Score breakdown by category"""
    technical_skills: float
    communication: float
    problem_solving: float
    behavioral: float


class InterviewReport(BaseModel):
    """Complete interview report"""
    id: int
    job_title: str
    date: datetime
    duration_minutes: Optional[int]
    overall_score: float
    category_scores: CategoryScore
    questions_and_answers: List[Dict[str, Any]]
    strengths: List[str]
    improvements: List[str]
    detailed_feedback: str
    share_token: Optional[str]
    is_public: bool

    class Config:
        from_attributes = True


class InterviewUsageResponse(BaseModel):
    """Current interview usage status"""
    sessions_used_today: int
    sessions_remaining: int
    max_sessions_per_day: int
    can_start_interview: bool
    next_reset: datetime  # Midnight tonight


# ===== Feedback Models =====

class FeedbackCreate(BaseModel):
    """Create new feedback/issue"""
    feedback_type: FeedbackType
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)
    page_url: Optional[str] = None
    browser_info: Optional[Dict[str, Any]] = None


class FeedbackResponse(BaseModel):
    """Feedback item response"""
    id: int
    user_id: int
    feedback_type: FeedbackType
    title: str
    description: str
    page_url: Optional[str] = None
    status: FeedbackStatus
    priority: Priority
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FeedbackListResponse(BaseModel):
    """List of feedback items"""
    items: List[FeedbackResponse]
    total: int


# ===== AI Response Models =====

class AIMessageResponse(BaseModel):
    """AI assistant's response to user message"""
    message: str
    suggestions: Optional[List[str]] = None  # Quick reply suggestions
    actions: Optional[List[Dict[str, str]]] = None  # Clickable actions


class HelpResponse(BaseModel):
    """Response for help mode"""
    answer: str
    related_articles: List[str] = []
    confidence_score: float = Field(..., ge=0, le=1)


# ===== Error Models =====

class ChatbotError(BaseModel):
    """Error response"""
    error: str
    code: str
    details: Optional[Dict[str, Any]] = None

"""
FastAPI Router for Chatbot System
Handles Help Mode, Interview Simulator, Chat Mode, and Feedback
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import google.generativeai as genai
import os
import json

from ..database import get_db, ChatSession, ChatMessage, InterviewSession, InterviewUsage, UserFeedback
from ..auth import get_current_user
from ..models.chatbot import (
    ChatSessionCreate,
    ChatMessageCreate,
    ChatMessage as ChatMessageModel,
    ChatSession as ChatSessionModel,
    InterviewStartRequest,
    InterviewAnswerRequest,
    InterviewReport,
    InterviewUsageResponse,
    FeedbackCreate,
    FeedbackResponse,
    SessionType,
    MessageRole,
    FeedbackType,
    FeedbackStatus,
    Priority,
    InterviewQuestion,
    QuestionEvaluation
)
from .rag_engine import get_rag_engine
from .interview_engine import get_interview_engine
from .prompts import HELP_SYSTEM_PROMPT, CHAT_SYSTEM_PROMPT, FEEDBACK_ANALYSIS_PROMPT
from .config import MAX_CHAT_MESSAGES_PER_HOUR, MAX_INTERVIEWS_PER_DAY

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/chatbot",
    tags=["chatbot"]
)

# Initialize Gemini
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)
model = genai.GenerativeModel(
    model_name=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
    generation_config={
        "temperature": 0.7,
        "top_p": 0.95,
        "max_output_tokens": 1024,
    }
)


# ============================================================================
# CHAT SESSIONS & MESSAGES
# ============================================================================

@router.post("/sessions/start", response_model=ChatSessionModel)
async def start_chat_session(
    session_data: ChatSessionCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start a new chat session (Help, Chat, or Feedback mode)
    """
    try:
        # Build metadata from optional fields
        metadata = {}
        if session_data.job_title:
            metadata['job_title'] = session_data.job_title
        if session_data.job_description:
            metadata['job_description'] = session_data.job_description
        
        # Create session
        session = ChatSession(
            user_id=current_user.id,
            session_type=session_data.session_type,
            session_metadata=metadata if metadata else None
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
        logger.info(f"Started {session_data.session_type} session {session.id} for user {current_user.id}")
        
        return ChatSessionModel.from_orm(session)
        
    except Exception as e:
        logger.error(f"Error starting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/message", response_model=ChatMessageModel)
async def send_message(
    session_id: int,
    message_data: ChatMessageCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Send a message and get AI response
    Handles Help mode (RAG), Chat mode (career advice), and Feedback mode
    """
    try:
        # Get session
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Rate limiting for chat mode
        if session.session_type == SessionType.CHAT:
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            recent_messages = db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id,
                ChatMessage.created_at >= one_hour_ago
            ).count()
            
            if recent_messages >= MAX_CHAT_MESSAGES_PER_HOUR:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Maximum {MAX_CHAT_MESSAGES_PER_HOUR} messages per hour."
                )
        
        # Save user message
        user_message = ChatMessage(
            session_id=session_id,
            role=MessageRole.USER,
            content=message_data.content
        )
        db.add(user_message)
        db.commit()
        
        # Generate AI response based on session type
        if session.session_type == SessionType.HELP:
            response_content = await _handle_help_message(message_data.content, db)
        elif session.session_type == SessionType.CHAT:
            response_content = await _handle_chat_message(session_id, message_data.content, db)
        elif session.session_type == SessionType.FEEDBACK:
            response_content = await _handle_feedback_message(message_data.content)
        else:
            raise HTTPException(status_code=400, detail="Invalid session type for messaging")
        
        # Save AI response
        ai_message = ChatMessage(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=response_content
        )
        db.add(ai_message)
        
        # Update session last activity
        session.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(ai_message)
        
        return ChatMessageModel.from_orm(ai_message)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_help_message(query: str, db: Session) -> str:
    """Handle Help mode message using RAG"""
    try:
        # Get RAG engine
        rag_engine = get_rag_engine()
        
        # Search knowledge base
        context = rag_engine.get_context_for_query(query)
        
        # Generate response with context
        prompt = f"""{HELP_SYSTEM_PROMPT}

{context}

User Question: {query}

Provide a helpful, concise answer based on the documentation above.
"""
        
        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        logger.error(f"Error in help mode: {e}")
        return "I apologize, but I'm having trouble accessing the help documentation right now. Please try again in a moment."


async def _handle_chat_message(session_id: int, message: str, db: Session) -> str:
    """Handle Chat mode message with conversation history"""
    try:
        # Get recent conversation history (last 10 messages)
        history = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.desc()).limit(10).all()
        
        history = list(reversed(history))  # Chronological order
        
        # Build conversation context
        context = "Conversation History:\n"
        for msg in history[:-1]:  # Exclude the message we just saved
            context += f"{msg.role.value}: {msg.content}\n"
        
        # Generate response
        prompt = f"""{CHAT_SYSTEM_PROMPT}

{context}

User: {message}

Provide career advice or answer the question:
"""
        
        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        logger.error(f"Error in chat mode: {e}")
        return "I apologize, but I'm having trouble processing your message. Please try again."


async def _handle_feedback_message(message: str) -> str:
    """Handle Feedback mode confirmation message"""
    return "Thank you for your feedback! Your message has been recorded and our team will review it shortly. Is there anything else you'd like to share?"


@router.get("/sessions/{session_id}/history", response_model=List[ChatMessageModel])
async def get_session_history(
    session_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all messages in a session"""
    # Verify session belongs to user
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get messages
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at).all()
    
    return [ChatMessageModel.from_orm(msg) for msg in messages]


# ============================================================================
# INTERVIEW SIMULATOR
# ============================================================================

@router.post("/interview/start")
async def start_interview(
    request: InterviewStartRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start a new interview session
    Checks rate limit and generates questions
    """
    try:
        # Check rate limit
        interview_engine = get_interview_engine()
        can_interview, remaining = interview_engine.check_rate_limit(current_user.id, db)
        
        if not can_interview:
            raise HTTPException(
                status_code=429,
                detail=f"Daily interview limit reached. You can do {MAX_INTERVIEWS_PER_DAY} interviews per day."
            )
        
        # Generate questions
        questions = interview_engine.generate_questions(
            job_description=request.job_description,
            job_title=request.job_title,
            company_name=request.company_name
        )
        
        # Create chat session for interview
        session = ChatSession(
            user_id=current_user.id,
            session_type=SessionType.INTERVIEW,
            session_metadata={
                "job_title": request.job_title,
                "company_name": request.company_name,
                "job_description": request.job_description,
                "questions": [q.dict() for q in questions],
                "current_question_index": 0,
                "start_time": datetime.utcnow().isoformat()
            }
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
        logger.info(f"Started interview session {session.id} for user {current_user.id}")
        
        return {
            "session_id": session.id,
            "total_questions": len(questions),
            "first_question": questions[0].dict(),
            "remaining_interviews_today": remaining - 1
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting interview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/interview/{session_id}/answer")
async def submit_answer(
    session_id: int,
    answer_data: InterviewAnswerRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit answer to current interview question
    Returns evaluation and next question (or follow-up)
    """
    try:
        # Get session
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.session_type == SessionType.INTERVIEW
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Interview session not found")
        
        metadata = session.session_metadata
        questions = [InterviewQuestion(**q) for q in metadata['questions']]
        current_index = metadata['current_question_index']
        
        if current_index >= len(questions):
            raise HTTPException(status_code=400, detail="Interview already completed")
        
        current_question = questions[current_index]
        
        # Get conversation history for this question
        conversation_key = f"question_{current_index}_history"
        if conversation_key not in metadata:
            metadata[conversation_key] = []
        
        # Add current Q&A to history
        metadata[conversation_key].append({
            "question": current_question.question,
            "answer": answer_data.answer
        })
        
        # Evaluate answer
        interview_engine = get_interview_engine()
        evaluation = interview_engine.evaluate_answer(
            question=current_question.question,
            answer=answer_data.answer,
            question_type=current_question.type,
            job_context=metadata['job_description'],
            conversation_history=metadata[conversation_key]
        )
        
        # Store evaluation
        eval_key = f"question_{current_index}_evaluation"
        metadata[eval_key] = evaluation.dict()
        
        # Determine next question
        next_question = None
        is_complete = False
        
        if evaluation.followup_question:
            # Return follow-up
            next_question = {
                "question": evaluation.followup_question,
                "type": current_question.type,
                "is_followup": True,
                "order": current_index + 1
            }
        else:
            # Move to next main question
            metadata['current_question_index'] = current_index + 1
            
            if metadata['current_question_index'] < len(questions):
                next_q = questions[metadata['current_question_index']]
                next_question = next_q.dict()
            else:
                is_complete = True
        
        # Update session
        session.session_metadata = metadata
        db.commit()
        
        response = {
            "evaluation": evaluation.dict(),
            "is_complete": is_complete,
            "next_question": next_question,
            "progress": {
                "current": current_index + 1,
                "total": len(questions)
            }
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting answer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/interview/{session_id}/complete", response_model=InterviewReport)
async def complete_interview(
    session_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Complete interview and generate report
    """
    try:
        # Get session
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.session_type == SessionType.INTERVIEW
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Interview session not found")
        
        metadata = session.session_metadata
        
        # Collect all questions and evaluations
        from ..models.chatbot import InterviewQuestion, QuestionEvaluation
        questions = [InterviewQuestion(**q) for q in metadata['questions']]
        
        questions_and_evals = []
        for i, question in enumerate(questions):
            eval_key = f"question_{i}_evaluation"
            history_key = f"question_{i}_history"
            
            if eval_key in metadata:
                evaluation = QuestionEvaluation(**metadata[eval_key])
                history = metadata.get(history_key, [])
                questions_and_evals.append((question, history, evaluation))
        
        if not questions_and_evals:
            raise HTTPException(status_code=400, detail="No answers submitted yet")
        
        # Calculate duration
        start_time = datetime.fromisoformat(metadata['start_time'])
        duration_minutes = int((datetime.utcnow() - start_time).total_seconds() / 60)
        
        # Generate report
        interview_engine = get_interview_engine()
        report = interview_engine.generate_interview_report(
            job_title=metadata['job_title'],
            company_name=metadata.get('company_name'),
            questions_and_evaluations=questions_and_evals,
            duration_minutes=duration_minutes
        )
        
        # Save to database
        interview_session = InterviewSession(
            user_id=current_user.id,
            job_title=metadata['job_title'],
            company_name=metadata.get('company_name'),
            overall_score=report.overall_score,
            category_scores=report.category_scores,
            feedback=report.dict(),
            share_token=report.share_token
        )
        db.add(interview_session)
        
        # Record usage - increment session count for today
        from datetime import date
        from sqlalchemy import func
        
        today = date.today()
        usage = db.query(InterviewUsage).filter(
            InterviewUsage.user_id == current_user.id,
            func.date(InterviewUsage.session_date) == today
        ).first()
        
        if usage:
            usage.session_count += 1
        else:
            usage = InterviewUsage(
                user_id=current_user.id,
                session_date=datetime.utcnow(),
                session_count=1
            )
            db.add(usage)
        
        db.commit()
        db.refresh(interview_session)
        
        logger.info(f"Interview {session_id} completed. Score: {report.overall_score}/10")
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing interview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/interview/usage", response_model=InterviewUsageResponse)
async def get_interview_usage(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's interview usage stats"""
    interview_engine = get_interview_engine()
    can_interview, remaining = interview_engine.check_rate_limit(current_user.id, db)
    
    # Calculate next reset time (midnight tonight)
    from datetime import datetime, timedelta
    tomorrow = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    
    return InterviewUsageResponse(
        sessions_used_today=MAX_INTERVIEWS_PER_DAY - remaining,
        sessions_remaining=remaining,
        max_sessions_per_day=MAX_INTERVIEWS_PER_DAY,
        can_start_interview=can_interview,
        next_reset=tomorrow
    )


@router.get("/interview/report/{share_token}")
async def get_shared_report(
    share_token: str,
    db: Session = Depends(get_db)
):
    """Get publicly shared interview report"""
    interview = db.query(InterviewSession).filter(
        InterviewSession.share_token == share_token
    ).first()
    
    if not interview:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return interview.feedback


# ============================================================================
# FEEDBACK SYSTEM
# ============================================================================

@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    feedback_data: FeedbackCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit bug report, feature request, or general feedback"""
    try:
        # Analyze feedback with AI to extract priority/severity
        analysis_prompt = f"""{FEEDBACK_ANALYSIS_PROMPT}

Feedback Type: {feedback_data.feedback_type}
Title: {feedback_data.title}
Description: {feedback_data.description}

Analyze and return JSON:
{{
  "priority": "low|medium|high|critical",
  "category": "UI/UX|Performance|Feature|Bug|Other"
}}
"""
        
        try:
            response = model.generate_content(analysis_prompt)
            analysis = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
            priority = Priority[analysis['priority'].upper()]
            category = analysis.get('category', 'Other')
        except:
            priority = Priority.MEDIUM
            category = "General"
        
        # Create feedback entry
        feedback = UserFeedback(
            user_id=current_user.id,
            feedback_type=feedback_data.feedback_type,
            title=feedback_data.title,
            description=feedback_data.description,
            priority=priority,
            status=FeedbackStatus.OPEN,
            feedback_metadata={"category": category}
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        
        logger.info(f"Feedback submitted: {feedback.id} ({feedback_data.feedback_type})")
        
        return FeedbackResponse.from_orm(feedback)
        
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feedback", response_model=List[FeedbackResponse])
async def get_user_feedback(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all feedback submitted by current user"""
    feedback_list = db.query(UserFeedback).filter(
        UserFeedback.user_id == current_user.id
    ).order_by(UserFeedback.created_at.desc()).all()
    
    return [FeedbackResponse.from_orm(f) for f in feedback_list]

"""
Interview Engine for AI Interview Simulator
Generates questions, evaluates answers, creates follow-ups, and generates reports
"""

import os
import json
import logging
import secrets
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import google.generativeai as genai

from ..models.chatbot import (
    InterviewQuestion,
    QuestionEvaluation,
    CategoryScore,
    InterviewReport
)
from .config import (
    MAX_QUESTIONS_PER_INTERVIEW,
    TECHNICAL_QUESTIONS,
    BEHAVIORAL_QUESTIONS,
    SITUATIONAL_QUESTIONS,
    MAX_FOLLOW_UPS_PER_QUESTION,
    SCORING_WEIGHTS
)
from .prompts import (
    INTERVIEW_QUESTION_GENERATION_PROMPT,
    INTERVIEW_SYSTEM_PROMPT,
    INTERVIEW_REPORT_PROMPT
)

logger = logging.getLogger(__name__)


class InterviewEngine:
    """
    Manages interview sessions: question generation, answer evaluation, follow-ups, reports
    """
    
    def __init__(self):
        # Initialize Gemini
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment")
        genai.configure(api_key=api_key)
        
        self.model = genai.GenerativeModel(
            model_name=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            generation_config={
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
        )
        
        logger.info("Interview Engine initialized")
    
    def generate_questions(
        self,
        job_description: str,
        job_title: str,
        company_name: Optional[str] = None
    ) -> List[InterviewQuestion]:
        """
        Generate interview questions based on job description
        
        Args:
            job_description: Full job description
            job_title: Job title/role
            company_name: Company name (optional)
        
        Returns:
            List of InterviewQuestion objects
        """
        logger.info(f"Generating {MAX_QUESTIONS_PER_INTERVIEW} questions for: {job_title}")
        
        # Build prompt
        context = f"Job Title: {job_title}\n"
        if company_name:
            context += f"Company: {company_name}\n"
        context += f"\nJob Description:\n{job_description}"
        
        prompt = f"""{INTERVIEW_QUESTION_GENERATION_PROMPT}

{context}

Generate exactly {MAX_QUESTIONS_PER_INTERVIEW} questions:
- {TECHNICAL_QUESTIONS} technical/skill-based questions
- {BEHAVIORAL_QUESTIONS} behavioral questions
- {SITUATIONAL_QUESTIONS} situational questions

Return a JSON array of questions with this exact format:
[
  {{
    "question": "Question text here",
    "type": "technical|behavioral|situational",
    "difficulty": "easy|medium|hard"
  }}
]
"""
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Extract JSON from response
            json_match = response_text
            if "```json" in response_text:
                json_match = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_match = response_text.split("```")[1].split("```")[0].strip()
            
            questions_data = json.loads(json_match)
            
            # Convert to InterviewQuestion objects
            questions = []
            for i, q_data in enumerate(questions_data[:MAX_QUESTIONS_PER_INTERVIEW], 1):
                question = InterviewQuestion(
                    order=i,
                    question=q_data['question'],
                    type=q_data['type'],
                    difficulty=q_data.get('difficulty', 'medium')
                )
                questions.append(question)
            
            logger.info(f"Successfully generated {len(questions)} questions")
            return questions
            
        except Exception as e:
            logger.error(f"Error generating questions: {e}")
            raise
    
    def evaluate_answer(
        self,
        question: str,
        answer: str,
        question_type: str,
        job_context: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> QuestionEvaluation:
        """
        Evaluate an interview answer and optionally generate follow-up
        
        Args:
            question: The interview question
            answer: User's answer
            question_type: technical/behavioral/situational
            job_context: Job description context
            conversation_history: Previous Q&A for this question (for follow-ups)
        
        Returns:
            QuestionEvaluation with scores and optional follow-up
        """
        logger.info(f"Evaluating answer for {question_type} question")
        
        # Determine if this is a follow-up (based on history length)
        follow_up_count = len(conversation_history) - 1 if conversation_history else 0
        can_generate_followup = follow_up_count < MAX_FOLLOW_UPS_PER_QUESTION
        
        # Build conversation context
        context = f"Job Context:\n{job_context}\n\n"
        
        if conversation_history:
            context += "Conversation History:\n"
            for i, entry in enumerate(conversation_history):
                context += f"Q{i+1}: {entry['question']}\n"
                context += f"A{i+1}: {entry['answer']}\n\n"
        
        # Build evaluation prompt
        prompt = f"""{INTERVIEW_SYSTEM_PROMPT}

{context}

Current Question: {question}
Question Type: {question_type}
Candidate's Answer: {answer}

Evaluate this answer and provide scores (0-10) for:
1. technical_accuracy: How technically correct and detailed is the answer?
2. communication: How clearly and professionally is it communicated?
3. problem_solving: Does it demonstrate analytical thinking?
4. real_world_application: Does it show practical experience?

Also provide:
- feedback: 2-3 sentences of constructive feedback
- should_followup: true/false - Does the answer warrant a follow-up question?
- followup_question: If should_followup is true AND we haven't exceeded {MAX_FOLLOW_UPS_PER_QUESTION} follow-ups, provide a relevant follow-up question

Current follow-up count: {follow_up_count}/{MAX_FOLLOW_UPS_PER_QUESTION}

Return ONLY a JSON object with this exact structure:
{{
  "technical_accuracy": 8,
  "communication": 7,
  "problem_solving": 8,
  "real_world_application": 6,
  "feedback": "Your feedback here",
  "should_followup": true,
  "followup_question": "Optional follow-up question here"
}}
"""
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Extract JSON
            json_match = response_text
            if "```json" in response_text:
                json_match = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_match = response_text.split("```")[1].split("```")[0].strip()
            
            eval_data = json.loads(json_match)
            
            # Create evaluation object
            evaluation = QuestionEvaluation(
                technical_accuracy=eval_data['technical_accuracy'],
                communication=eval_data['communication'],
                problem_solving=eval_data['problem_solving'],
                real_world_application=eval_data['real_world_application'],
                feedback=eval_data['feedback'],
                followup_question=eval_data.get('followup_question') if (
                    eval_data.get('should_followup') and can_generate_followup
                ) else None
            )
            
            logger.info(f"Evaluation complete. Average score: {evaluation.average_score:.1f}")
            return evaluation
            
        except Exception as e:
            logger.error(f"Error evaluating answer: {e}")
            raise
    
    def calculate_category_scores(
        self,
        all_evaluations: List[QuestionEvaluation]
    ) -> List[CategoryScore]:
        """
        Calculate weighted category scores from all evaluations
        
        Args:
            all_evaluations: List of all question evaluations
        
        Returns:
            List of CategoryScore objects
        """
        if not all_evaluations:
            return []
        
        # Average scores across all questions
        avg_technical = sum(e.technical_accuracy for e in all_evaluations) / len(all_evaluations)
        avg_communication = sum(e.communication for e in all_evaluations) / len(all_evaluations)
        avg_problem_solving = sum(e.problem_solving for e in all_evaluations) / len(all_evaluations)
        avg_real_world = sum(e.real_world_application for e in all_evaluations) / len(all_evaluations)
        
        return [
            CategoryScore(
                category="Technical Skills",
                score=round(avg_technical, 1),
                weight=SCORING_WEIGHTS['technical'],
                feedback=self._generate_category_feedback("technical", avg_technical)
            ),
            CategoryScore(
                category="Communication",
                score=round(avg_communication, 1),
                weight=SCORING_WEIGHTS['communication'],
                feedback=self._generate_category_feedback("communication", avg_communication)
            ),
            CategoryScore(
                category="Problem Solving",
                score=round(avg_problem_solving, 1),
                weight=SCORING_WEIGHTS['problem_solving'],
                feedback=self._generate_category_feedback("problem_solving", avg_problem_solving)
            ),
            CategoryScore(
                category="Real-World Application",
                score=round(avg_real_world, 1),
                weight=SCORING_WEIGHTS['real_world'],
                feedback=self._generate_category_feedback("real_world", avg_real_world)
            )
        ]
    
    def _generate_category_feedback(self, category: str, score: float) -> str:
        """Generate feedback based on category and score"""
        if score >= 8:
            level = "Excellent"
        elif score >= 6:
            level = "Good"
        elif score >= 4:
            level = "Fair"
        else:
            level = "Needs improvement"
        
        feedback_templates = {
            "technical": f"{level} technical knowledge demonstrated.",
            "communication": f"{level} communication clarity.",
            "problem_solving": f"{level} analytical thinking shown.",
            "real_world": f"{level} practical application experience."
        }
        
        return feedback_templates.get(category, f"{level} performance.")
    
    def generate_interview_report(
        self,
        job_title: str,
        company_name: Optional[str],
        questions_and_evaluations: List[Tuple[InterviewQuestion, List[Dict], QuestionEvaluation]],
        duration_minutes: int
    ) -> InterviewReport:
        """
        Generate comprehensive interview report
        
        Args:
            job_title: Job title
            company_name: Company name
            questions_and_evaluations: List of (question, conversation_history, evaluation) tuples
            duration_minutes: Interview duration
        
        Returns:
            InterviewReport object
        """
        logger.info("Generating interview report")
        
        # Extract all evaluations
        all_evaluations = [eval for _, _, eval in questions_and_evaluations]
        
        # Calculate category scores
        category_scores = self.calculate_category_scores(all_evaluations)
        
        # Calculate overall score (weighted average)
        overall_score = sum(
            cat.score * cat.weight / 100
            for cat in category_scores
        )
        
        # Generate detailed feedback using AI
        feedback_prompt = f"""{INTERVIEW_REPORT_PROMPT}

Job Title: {job_title}
Company: {company_name or 'N/A'}
Duration: {duration_minutes} minutes
Questions Answered: {len(questions_and_evaluations)}

Category Scores:
{chr(10).join(f"- {cat.category}: {cat.score}/10 (weight: {cat.weight}%)" for cat in category_scores)}

Overall Score: {overall_score:.1f}/10

Question Details:
"""
        
        for i, (question, history, evaluation) in enumerate(questions_and_evaluations, 1):
            feedback_prompt += f"\nQ{i}: {question.question}\n"
            feedback_prompt += f"Type: {question.type}, Difficulty: {question.difficulty}\n"
            feedback_prompt += f"Scores: Tech={evaluation.technical_accuracy}, Comm={evaluation.communication}, "
            feedback_prompt += f"Problem={evaluation.problem_solving}, RealWorld={evaluation.real_world_application}\n"
            feedback_prompt += f"Feedback: {evaluation.feedback}\n"
        
        feedback_prompt += """\n
Based on this interview performance, provide:
1. A list of 3-5 key strengths (each 1 sentence)
2. A list of 3-5 areas for improvement (each 1 sentence)
3. 2-3 specific recommendations for the candidate

Return as JSON:
{
  "strengths": ["strength 1", "strength 2", ...],
  "improvements": ["improvement 1", "improvement 2", ...],
  "recommendations": ["recommendation 1", "recommendation 2", ...]
}
"""
        
        try:
            response = self.model.generate_content(feedback_prompt)
            response_text = response.text.strip()
            
            # Extract JSON
            json_match = response_text
            if "```json" in response_text:
                json_match = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_match = response_text.split("```")[1].split("```")[0].strip()
            
            detailed_feedback = json.loads(json_match)
            
            # Generate shareable token
            share_token = secrets.token_urlsafe(32)
            
            # Create report
            report = InterviewReport(
                job_title=job_title,
                company_name=company_name,
                overall_score=round(overall_score, 1),
                category_scores=category_scores,
                strengths=detailed_feedback['strengths'],
                improvements=detailed_feedback['improvements'],
                recommendations=detailed_feedback['recommendations'],
                total_questions=len(questions_and_evaluations),
                duration_minutes=duration_minutes,
                share_token=share_token
            )
            
            logger.info(f"Report generated. Overall score: {overall_score:.1f}/10")
            return report
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            # Fallback to basic report
            return InterviewReport(
                job_title=job_title,
                company_name=company_name,
                overall_score=round(overall_score, 1),
                category_scores=category_scores,
                strengths=["Completed interview"],
                improvements=["Review performance"],
                recommendations=["Continue practicing"],
                total_questions=len(questions_and_evaluations),
                duration_minutes=duration_minutes,
                share_token=secrets.token_urlsafe(32)
            )
    
    def check_rate_limit(self, user_id: int, db) -> Tuple[bool, int]:
        """
        Check if user has exceeded daily interview limit
        
        Args:
            user_id: User ID
            db: Database session
        
        Returns:
            Tuple of (can_interview: bool, remaining_count: int)
        """
        from datetime import date
        from sqlalchemy import func
        from ..database import InterviewUsage
        
        today = date.today()
        
        # Get usage record for today
        usage = db.query(InterviewUsage).filter(
            InterviewUsage.user_id == user_id,
            func.date(InterviewUsage.session_date) == today
        ).first()
        
        count = usage.session_count if usage else 0
        
        from .config import MAX_INTERVIEWS_PER_DAY
        remaining = MAX_INTERVIEWS_PER_DAY - count
        can_interview = remaining > 0
        
        logger.info(f"Rate limit check for user {user_id}: {count}/{MAX_INTERVIEWS_PER_DAY} used")
        
        return can_interview, max(0, remaining)


# Global singleton
_interview_engine: InterviewEngine = None


def get_interview_engine() -> InterviewEngine:
    """Get or create interview engine singleton"""
    global _interview_engine
    if _interview_engine is None:
        _interview_engine = InterviewEngine()
    return _interview_engine

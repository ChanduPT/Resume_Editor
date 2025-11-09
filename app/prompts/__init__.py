"""
Prompts package for resume optimization
"""

from .jd_hints import JD_HINTS_PROMPT, jd_hints_response_schema
from .summary import GENERATE_SUMMARY_FROM_JD_PROMPT, summary_response_schema
from .experience import GENERATE_EXPERIENCE_BULLETS_FROM_JD_PROMPT, experience_response_schema
from .skills import GENERATE_TECHNICAL_SKILLS_FROM_JD, skills_response_schema

# Alias for backward compatibility
GENERATE_EXPERIENCE_FROM_JD_PROMPT = GENERATE_EXPERIENCE_BULLETS_FROM_JD_PROMPT

# Import legacy prompts from old prompts.py file for utils.py
import importlib.util
import os
_prompts_file = os.path.join(os.path.dirname(__file__), '..', 'prompts.py')
_spec = importlib.util.spec_from_file_location('_old_prompts', _prompts_file)
_old_prompts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_old_prompts)

PARSE_EXPERIENCE_PROMPT = _old_prompts.PARSE_EXPERIENCE_PROMPT
PARSE_SKILLS_PROMPT = _old_prompts.PARSE_SKILLS_PROMPT
SCORING_PROMPT_JSON = _old_prompts.SCORING_PROMPT_JSON
APPLY_EDITS_PROMPT = _old_prompts.APPLY_EDITS_PROMPT
BALANCE_BULLETS_PROMPT = _old_prompts.BALANCE_BULLETS_PROMPT
ORGANIZE_SKILLS_PROMPT = _old_prompts.ORGANIZE_SKILLS_PROMPT
GENERATE_FROM_JD_PROMPT = _old_prompts.GENERATE_FROM_JD_PROMPT
PARSE_RESUME_TEXT_PROMPT = _old_prompts.PARSE_RESUME_TEXT_PROMPT

__all__ = [
    'JD_HINTS_PROMPT',
    'jd_hints_response_schema',
    'GENERATE_SUMMARY_FROM_JD_PROMPT',
    'summary_response_schema',
    'GENERATE_EXPERIENCE_FROM_JD_PROMPT',
    'GENERATE_EXPERIENCE_BULLETS_FROM_JD_PROMPT',
    'experience_response_schema',
    'GENERATE_TECHNICAL_SKILLS_FROM_JD',
    'skills_response_schema',
    'PARSE_EXPERIENCE_PROMPT',
    'PARSE_SKILLS_PROMPT',
    'SCORING_PROMPT_JSON',
    'APPLY_EDITS_PROMPT',
    'BALANCE_BULLETS_PROMPT',
    'ORGANIZE_SKILLS_PROMPT',
    'GENERATE_FROM_JD_PROMPT',
    'PARSE_RESUME_TEXT_PROMPT'
]

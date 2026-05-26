# app/create_pdf.py
# PDF Resume Generator - matches Word classic format (Times New Roman, ATS-friendly)

import logging
from io import BytesIO
from typing import Dict, Any

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, HRFlowable
from reportlab.lib.styles import ParagraphStyle

logger = logging.getLogger(__name__)

# Built-in PDF font equivalents of Times New Roman
_NORMAL = 'Times-Roman'
_BOLD   = 'Times-Bold'


def _s(name, **kw):
    """Create a ParagraphStyle with sensible defaults."""
    defaults = dict(fontName=_NORMAL, fontSize=10, leading=13,
                    spaceBefore=0, spaceAfter=0)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)


def _build_story(data: dict) -> list:
    story = []

    # ── Name ──────────────────────────────────────────────────────────────
    name_s = _s('Name', fontName=_BOLD, fontSize=12, leading=15,
                alignment=TA_CENTER, spaceAfter=2)
    story.append(Paragraph(data.get('name', ''), name_s))

    # ── Contact ───────────────────────────────────────────────────────────
    contact_data = data.get('contact', {})
    if isinstance(contact_data, dict):
        ordered_keys = ["phone", "email", "location",
                        "linkedin", "github", "portfolio", "website"]
        parts = []
        for key in ordered_keys:
            if key in contact_data and contact_data[key]:
                # Show actual value for phone/email/location; key name for links
                if key in ("phone", "email", "location"):
                    parts.append(str(contact_data[key]))
                else:
                    parts.append(key.capitalize())
        for key, val in contact_data.items():
            if key not in ordered_keys and val:
                parts.append(str(val))
        contact_text = " | ".join(parts)
    else:
        contact_text = str(contact_data) if contact_data else ''

    if contact_text:
        contact_s = _s('Contact', alignment=TA_CENTER, leading=12, spaceAfter=6)
        story.append(Paragraph(contact_text, contact_s))

    # ── Section heading helper (ALL CAPS bold + horizontal rule) ──────────
    def section(title):
        hdr_s = _s(f'Hdr_{title}', fontName=_BOLD, fontSize=11, leading=14,
                   spaceBefore=8, spaceAfter=1)
        story.append(Paragraph(title, hdr_s))
        story.append(HRFlowable(width='100%', thickness=0.5,
                                color='black', spaceAfter=3))

    body_s   = _s('Body',   spaceAfter=4, alignment=TA_JUSTIFY)
    bullet_s = _s('Bullet', leftIndent=15, firstLineIndent=-10, spaceAfter=2)
    bold_s   = _s('Bold',   fontName=_BOLD, fontSize=11, leading=14,
                  spaceBefore=6, spaceAfter=2)
    plain_s  = _s('Plain',  spaceAfter=3)

    # ── Professional Summary ───────────────────────────────────────────────
    if data.get('summary'):
        section('PROFESSIONAL SUMMARY')
        story.append(Paragraph(data['summary'], body_s))

    # ── Technical Skills ──────────────────────────────────────────────────
    skills = data.get('technical_skills') or data.get('skills')
    if skills:
        section('TECHNICAL SKILLS')
        skill_s = _s('Skill', spaceAfter=3)
        for category, vals in skills.items():
            if isinstance(vals, list):
                vals_text = ', '.join(str(v) for v in vals)
            elif isinstance(vals, dict):
                vals_text = '; '.join(
                    f"{k}: {', '.join(v) if isinstance(v, list) else str(v)}"
                    for k, v in vals.items()
                )
            else:
                vals_text = str(vals)
            story.append(Paragraph(f'<b>{category}:</b> {vals_text}', skill_s))

    # ── Work Experience ────────────────────────────────────────────────────
    if data.get('experience'):
        section('WORK EXPERIENCE')
        for exp in data['experience']:
            job_title = exp.get('role') or exp.get('title', 'Position')
            dates = (exp.get('period') or exp.get('dates')
                     or exp.get('duration', ''))
            line = f"{exp.get('company', '')} | {job_title}"
            if dates:
                line += f" | {dates}"
            story.append(Paragraph(line, bold_s))
            for point in (exp.get('points') or exp.get('bullets') or []):
                story.append(Paragraph(f'• {point}', bullet_s))

    # ── Projects ──────────────────────────────────────────────────────────
    if data.get('projects'):
        section('PROJECTS')
        proj_bold_s = _s('ProjBold', fontName=_BOLD, fontSize=11, leading=14,
                         spaceBefore=6, spaceAfter=2)
        for proj in data['projects']:
            title = proj.get('name') or proj.get('title', '')
            if title:
                story.append(Paragraph(title, proj_bold_s))
            if proj.get('description'):
                story.append(Paragraph(proj['description'], body_s))
            for point in (proj.get('points') or proj.get('bullets') or []):
                story.append(Paragraph(f'• {point}', bullet_s))

    # ── Education ─────────────────────────────────────────────────────────
    if data.get('education'):
        section('EDUCATION')
        for edu in data['education']:
            text = edu.get('degree', '')
            if edu.get('institution'):
                text += f", {edu['institution']}"
            if edu.get('year'):
                text += f" ({edu['year']})"
            story.append(Paragraph(text, plain_s))

    # ── Certifications ────────────────────────────────────────────────────
    if data.get('certifications'):
        section('CERTIFICATIONS')
        for cert in data['certifications']:
            if cert.get('name'):
                text = cert['name']
                issuer = cert.get('issuer') or cert.get('organization', '')
                if issuer:
                    text += f", {issuer}"
                if cert.get('year'):
                    text += f" ({cert['year']})"
                story.append(Paragraph(text, plain_s))

    return story


def _make_doc(target, **kwargs):
    return SimpleDocTemplate(
        target,
        pagesize=letter,
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        **kwargs
    )


def create_resume_pdf(data: Dict[str, Any], output_path: str) -> str:
    """Create a PDF resume matching Word classic format and save to output_path."""
    doc = _make_doc(output_path)
    doc.build(_build_story(data))
    return output_path


def create_resume_pdf_bytes(data: Dict[str, Any]) -> bytes:
    """Create a PDF resume matching Word classic format and return as bytes."""
    buffer = BytesIO()
    doc = _make_doc(buffer)
    doc.build(_build_story(data))
    buffer.seek(0)
    return buffer.read()

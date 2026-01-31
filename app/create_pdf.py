# app/create_pdf.py
# PDF Resume Generator using ReportLab

import os
import logging
from io import BytesIO
from typing import Dict, Any, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, ListFlowable, ListItem
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

logger = logging.getLogger(__name__)


def create_resume_pdf(data: Dict[str, Any], output_path: str) -> str:
    """
    Create a professional PDF resume from resume data.
    
    Args:
        data: Resume data dictionary
        output_path: Path to save the PDF file
    
    Returns:
        Path to the created PDF file
    """
    
    # Create the document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )
    
    # Define custom styles
    styles = getSampleStyleSheet()
    
    # Name style (large, bold)
    styles.add(ParagraphStyle(
        name='ResumeName',
        parent=styles['Heading1'],
        fontSize=22,
        leading=26,
        alignment=TA_CENTER,
        spaceAfter=4,
        textColor=colors.HexColor('#1a1a2e')
    ))
    
    # Contact info style
    styles.add(ParagraphStyle(
        name='ContactInfo',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        alignment=TA_CENTER,
        spaceAfter=12,
        textColor=colors.HexColor('#4a5568')
    ))
    
    # Section header style
    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading2'],
        fontSize=12,
        leading=16,
        spaceBefore=12,
        spaceAfter=6,
        textColor=colors.HexColor('#2d3748'),
        borderPadding=(0, 0, 3, 0)
    ))
    
    # Company/Role style
    styles.add(ParagraphStyle(
        name='CompanyRole',
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
        spaceBefore=6,
        spaceAfter=2,
        textColor=colors.HexColor('#1a1a2e')
    ))
    
    # Period style
    styles.add(ParagraphStyle(
        name='Period',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        textColor=colors.HexColor('#718096')
    ))
    
    # Body text style
    styles.add(ParagraphStyle(
        name='BodyText',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
        textColor=colors.HexColor('#2d3748')
    ))
    
    # Bullet point style
    styles.add(ParagraphStyle(
        name='BulletPoint',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        leftIndent=15,
        spaceAfter=3,
        textColor=colors.HexColor('#2d3748')
    ))
    
    # Build the document content
    story = []
    
    # Name
    name = data.get('name', 'Your Name')
    story.append(Paragraph(name, styles['ResumeName']))
    
    # Contact info
    contact = data.get('contact', {})
    if contact:
        contact_parts = []
        if isinstance(contact, dict):
            for key, value in contact.items():
                if value:
                    contact_parts.append(str(value))
        elif isinstance(contact, str):
            contact_parts.append(contact)
        
        if contact_parts:
            contact_text = ' | '.join(contact_parts)
            story.append(Paragraph(contact_text, styles['ContactInfo']))
    
    # Summary
    summary = data.get('summary', '')
    if summary:
        story.append(create_section_header('PROFESSIONAL SUMMARY', styles))
        story.append(Paragraph(summary, styles['BodyText']))
    
    # Technical Skills
    skills = data.get('technical_skills', {})
    if skills:
        story.append(create_section_header('TECHNICAL SKILLS', styles))
        
        skills_data = []
        for category, skill_list in skills.items():
            if isinstance(skill_list, list):
                skill_text = ', '.join(skill_list)
            else:
                skill_text = str(skill_list)
            skills_data.append([f"<b>{category}:</b>", skill_text])
        
        if skills_data:
            for skill_row in skills_data:
                skill_para = Paragraph(f"{skill_row[0]} {skill_row[1]}", styles['BodyText'])
                story.append(skill_para)
    
    # Experience
    experience = data.get('experience', [])
    if experience:
        story.append(create_section_header('PROFESSIONAL EXPERIENCE', styles))
        
        for exp in experience:
            company = exp.get('company', '')
            role = exp.get('role', '')
            period = exp.get('period', '')
            points = exp.get('points', [])
            
            # Company and Role
            exp_header = f"<b>{role}</b> at <b>{company}</b>"
            story.append(Paragraph(exp_header, styles['CompanyRole']))
            
            # Period
            if period:
                story.append(Paragraph(period, styles['Period']))
            
            story.append(Spacer(1, 4))
            
            # Bullet points
            for point in points:
                if point:
                    bullet_text = f"• {point}"
                    story.append(Paragraph(bullet_text, styles['BulletPoint']))
            
            story.append(Spacer(1, 6))
    
    # Education
    education = data.get('education', [])
    if education:
        story.append(create_section_header('EDUCATION', styles))
        
        for edu in education:
            degree = edu.get('degree', '')
            institution = edu.get('institution', '')
            year = edu.get('year', '')
            
            edu_text = f"<b>{degree}</b> - {institution}"
            if year:
                edu_text += f" ({year})"
            story.append(Paragraph(edu_text, styles['BodyText']))
    
    # Projects
    projects = data.get('projects', [])
    if projects:
        story.append(create_section_header('PROJECTS', styles))
        
        for proj in projects:
            title = proj.get('title', '')
            bullets = proj.get('bullets', [])
            
            if title:
                story.append(Paragraph(f"<b>{title}</b>", styles['CompanyRole']))
                
                for bullet in bullets:
                    if bullet:
                        bullet_text = f"• {bullet}"
                        story.append(Paragraph(bullet_text, styles['BulletPoint']))
                
                story.append(Spacer(1, 4))
    
    # Certifications
    certifications = data.get('certifications', [])
    if certifications:
        story.append(create_section_header('CERTIFICATIONS', styles))
        
        for cert in certifications:
            cert_name = cert.get('name', '')
            cert_org = cert.get('organization', '')
            cert_year = cert.get('year', '')
            
            cert_text = f"<b>{cert_name}</b>"
            if cert_org:
                cert_text += f" - {cert_org}"
            if cert_year:
                cert_text += f" ({cert_year})"
            story.append(Paragraph(cert_text, styles['BodyText']))
    
    # Build PDF
    doc.build(story)
    
    logger.info(f"PDF resume created: {output_path}")
    return output_path


def create_section_header(title: str, styles) -> List:
    """Create a styled section header with horizontal line."""
    return Paragraph(
        f"<u>{title}</u>",
        styles['SectionHeader']
    )


def create_resume_pdf_bytes(data: Dict[str, Any]) -> bytes:
    """
    Create a PDF resume and return as bytes.
    
    Args:
        data: Resume data dictionary
    
    Returns:
        PDF content as bytes
    """
    buffer = BytesIO()
    
    # Create the document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )
    
    # Define custom styles
    styles = getSampleStyleSheet()
    
    # Name style (large, bold)
    styles.add(ParagraphStyle(
        name='ResumeName',
        parent=styles['Heading1'],
        fontSize=22,
        leading=26,
        alignment=TA_CENTER,
        spaceAfter=4,
        textColor=colors.HexColor('#1a1a2e')
    ))
    
    # Contact info style
    styles.add(ParagraphStyle(
        name='ContactInfo',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        alignment=TA_CENTER,
        spaceAfter=12,
        textColor=colors.HexColor('#4a5568')
    ))
    
    # Section header style
    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading2'],
        fontSize=12,
        leading=16,
        spaceBefore=12,
        spaceAfter=6,
        textColor=colors.HexColor('#2d3748'),
        borderPadding=(0, 0, 3, 0)
    ))
    
    # Company/Role style
    styles.add(ParagraphStyle(
        name='CompanyRole',
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
        spaceBefore=6,
        spaceAfter=2,
        textColor=colors.HexColor('#1a1a2e')
    ))
    
    # Period style
    styles.add(ParagraphStyle(
        name='Period',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        textColor=colors.HexColor('#718096')
    ))
    
    # Body text style
    styles.add(ParagraphStyle(
        name='BodyText',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
        textColor=colors.HexColor('#2d3748')
    ))
    
    # Bullet point style
    styles.add(ParagraphStyle(
        name='BulletPoint',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        leftIndent=15,
        spaceAfter=3,
        textColor=colors.HexColor('#2d3748')
    ))
    
    # Build the document content
    story = []
    
    # Name
    name = data.get('name', 'Your Name')
    story.append(Paragraph(name, styles['ResumeName']))
    
    # Contact info
    contact = data.get('contact', {})
    if contact:
        contact_parts = []
        if isinstance(contact, dict):
            for key, value in contact.items():
                if value:
                    contact_parts.append(str(value))
        elif isinstance(contact, str):
            contact_parts.append(contact)
        
        if contact_parts:
            contact_text = ' | '.join(contact_parts)
            story.append(Paragraph(contact_text, styles['ContactInfo']))
    
    # Summary
    summary = data.get('summary', '')
    if summary:
        story.append(Paragraph("<u>PROFESSIONAL SUMMARY</u>", styles['SectionHeader']))
        story.append(Paragraph(summary, styles['BodyText']))
    
    # Technical Skills
    skills = data.get('technical_skills', {})
    if skills:
        story.append(Paragraph("<u>TECHNICAL SKILLS</u>", styles['SectionHeader']))
        
        for category, skill_list in skills.items():
            if isinstance(skill_list, list):
                skill_text = ', '.join(skill_list)
            else:
                skill_text = str(skill_list)
            skill_para = Paragraph(f"<b>{category}:</b> {skill_text}", styles['BodyText'])
            story.append(skill_para)
    
    # Experience
    experience = data.get('experience', [])
    if experience:
        story.append(Paragraph("<u>PROFESSIONAL EXPERIENCE</u>", styles['SectionHeader']))
        
        for exp in experience:
            company = exp.get('company', '')
            role = exp.get('role', '')
            period = exp.get('period', '')
            points = exp.get('points', [])
            
            # Company and Role
            exp_header = f"<b>{role}</b> at <b>{company}</b>"
            story.append(Paragraph(exp_header, styles['CompanyRole']))
            
            # Period
            if period:
                story.append(Paragraph(period, styles['Period']))
            
            story.append(Spacer(1, 4))
            
            # Bullet points
            for point in points:
                if point:
                    bullet_text = f"• {point}"
                    story.append(Paragraph(bullet_text, styles['BulletPoint']))
            
            story.append(Spacer(1, 6))
    
    # Education
    education = data.get('education', [])
    if education:
        story.append(Paragraph("<u>EDUCATION</u>", styles['SectionHeader']))
        
        for edu in education:
            degree = edu.get('degree', '')
            institution = edu.get('institution', '')
            year = edu.get('year', '')
            
            edu_text = f"<b>{degree}</b> - {institution}"
            if year:
                edu_text += f" ({year})"
            story.append(Paragraph(edu_text, styles['BodyText']))
    
    # Projects
    projects = data.get('projects', [])
    if projects:
        story.append(Paragraph("<u>PROJECTS</u>", styles['SectionHeader']))
        
        for proj in projects:
            title = proj.get('title', '')
            bullets = proj.get('bullets', [])
            
            if title:
                story.append(Paragraph(f"<b>{title}</b>", styles['CompanyRole']))
                
                for bullet in bullets:
                    if bullet:
                        bullet_text = f"• {bullet}"
                        story.append(Paragraph(bullet_text, styles['BulletPoint']))
                
                story.append(Spacer(1, 4))
    
    # Certifications
    certifications = data.get('certifications', [])
    if certifications:
        story.append(Paragraph("<u>CERTIFICATIONS</u>", styles['SectionHeader']))
        
        for cert in certifications:
            cert_name = cert.get('name', '')
            cert_org = cert.get('organization', '')
            cert_year = cert.get('year', '')
            
            cert_text = f"<b>{cert_name}</b>"
            if cert_org:
                cert_text += f" - {cert_org}"
            if cert_year:
                cert_text += f" ({cert_year})"
            story.append(Paragraph(cert_text, styles['BodyText']))
    
    # Build PDF
    doc.build(story)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes


if __name__ == "__main__":
    # Test with sample data
    sample_data = {
        "name": "John Doe",
        "contact": {
            "email": "john.doe@email.com",
            "phone": "+1 (555) 123-4567",
            "linkedin": "linkedin.com/in/johndoe"
        },
        "summary": "Experienced software engineer with 5+ years of expertise in full-stack development.",
        "technical_skills": {
            "Languages": ["Python", "JavaScript", "TypeScript"],
            "Frameworks": ["React", "Node.js", "FastAPI"]
        },
        "experience": [
            {
                "company": "Tech Corp",
                "role": "Senior Software Engineer",
                "period": "Jan 2022 - Present",
                "points": [
                    "Led development of microservices architecture",
                    "Improved system performance by 40%"
                ]
            }
        ],
        "education": [
            {
                "degree": "B.S. Computer Science",
                "institution": "University of Technology",
                "year": "2018"
            }
        ]
    }
    
    create_resume_pdf(sample_data, "test_resume.pdf")
    print("Test PDF created: test_resume.pdf")

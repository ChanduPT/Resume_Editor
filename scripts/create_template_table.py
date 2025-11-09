#!/usr/bin/env python3
"""
Create the user_resume_templates table
"""
from app.database import Base, engine

print("Creating user_resume_templates table...")
Base.metadata.create_all(bind=engine)
print("✅ Table created successfully!")

"""
Migration: create llm_call_logs table.
Run once:  python scripts/migrate_llm_call_logs.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import engine, Base, LLMCallLog
from sqlalchemy import inspect, text

def run():
    insp = inspect(engine)
    if "llm_call_logs" in insp.get_table_names():
        print("✓ llm_call_logs table already exists — nothing to do.")
        return

    print("Creating llm_call_logs table …")
    LLMCallLog.__table__.create(bind=engine)
    print("✓ Done.")

if __name__ == "__main__":
    run()

# Database Migrations

## Issue on Render Deployment

The application fails on startup with:
```
column resume_jobs.format does not exist
```

This happens because the production database on Render is missing columns that were added to the SQLAlchemy model.

## Solution

Run the migration script to add missing columns to the `resume_jobs` table.

### Option 1: Python Migration Script (Recommended)

This script automatically checks and adds missing columns without requiring psql.

**On Render Shell:**
```bash
python3 migrate_database.py
```

**Locally:**
```bash
# Set your DATABASE_URL first
export DATABASE_URL="postgresql://user:pass@host:port/dbname"
python3 migrate_database.py
```

### Option 2: SQL Migration Files

If you prefer manual SQL execution:

**On Render Shell:**
```bash
# Install PostgreSQL client
apt-get update && apt-get install -y postgresql-client

# Run migrations
psql "$DATABASE_URL" -f migrations/add_feedback_columns.sql
psql "$DATABASE_URL" -f migrations/add_format_column.sql
```

**Or use the bash script:**
```bash
chmod +x run_migrations.sh
./run_migrations.sh
```

## What Gets Added

The migration adds these columns to `resume_jobs` table:

1. **format** (VARCHAR(50), default: 'classic')
   - Stores resume format preference: "classic" or "modern"
   
2. **intermediate_state** (JSON, nullable)
   - Stores extracted JD keywords for user review
   
3. **feedback_submitted_at** (TIMESTAMP, nullable)
   - Timestamp when user submitted feedback

4. **Index: idx_status_created_at**
   - Composite index on (status, created_at) for efficient cleanup queries

## Verification

After running the migration, verify the schema:

```sql
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'resume_jobs'
ORDER BY ordinal_position;
```

Expected output should include all columns listed above.

## How to Run on Render

1. Go to your Render dashboard
2. Navigate to your web service
3. Click "Shell" tab
4. Run:
   ```bash
   python3 migrate_database.py
   ```

The migration script is **idempotent** - it's safe to run multiple times. It will only add columns that don't exist.

## After Migration

After successful migration:
1. Restart your web service on Render
2. The application should start without errors
3. Check logs to confirm startup: `✅ Database initialized successfully`

## Automatic Migrations on Render

To run migrations automatically on every deploy, add this to your `render.yaml`:

```yaml
services:
  - type: web
    name: resume-editor
    buildCommand: "pip install -r requirements.txt && python3 migrate_database.py"
    startCommand: "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
```

Or create a pre-deploy hook in `Procfile`:
```
release: python3 migrate_database.py
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Notes

- The migration script uses SQLAlchemy to connect, so it works with the same DATABASE_URL environment variable
- All migrations are wrapped in transactions for safety
- If a column already exists, it will be skipped (no errors)
- The script provides detailed output showing what was added

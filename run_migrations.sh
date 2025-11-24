#!/bin/bash
# Script to run database migrations on Render
# Run this manually via Render Shell

set -e

echo "Starting database migration..."

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL environment variable is not set"
    exit 1
fi

# Install psql if not available
if ! command -v psql &> /dev/null; then
    echo "Installing PostgreSQL client..."
    apt-get update && apt-get install -y postgresql-client
fi

# Run migrations in order
echo "Running migration: add_feedback_columns.sql"
psql "$DATABASE_URL" -f migrations/add_feedback_columns.sql

echo "Running migration: add_format_column.sql"
psql "$DATABASE_URL" -f migrations/add_format_column.sql

echo "All migrations completed successfully!"

# Show current schema
echo ""
echo "Current resume_jobs table schema:"
psql "$DATABASE_URL" -c "\d resume_jobs"

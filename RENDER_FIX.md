# 🚨 URGENT FIX - Render Deployment Error

## Error Message
```
column resume_jobs.format does not exist
```

## Quick Fix (5 minutes)

### Step 1: Open Render Shell
1. Go to https://dashboard.render.com
2. Click on your **resume-editor** service
3. Click the **"Shell"** tab at the top

### Step 2: Run Migration
Copy and paste this command:
```bash
python3 migrate_database.py
```

### Step 3: Verify Success
You should see:
```
✅ All migrations completed successfully!
```

### Step 4: Restart (Automatic)
The service will restart automatically after shell closes.

## What This Does

Adds missing columns to the database:
- ✅ `format` column (classic/modern resume styles)
- ✅ `intermediate_state` column (keyword review feature)
- ✅ `feedback_submitted_at` column (feedback tracking)
- ✅ Index for performance optimization

## Verification

After restart, check logs in Render Dashboard:
- ✅ Look for: `Database initialized successfully`
- ❌ No more: `column resume_jobs.format does not exist`

## Alternative: SQL Method

If Python script fails, use SQL directly:

```bash
# Install psql
apt-get update && apt-get install -y postgresql-client

# Run migrations
psql "$DATABASE_URL" -f migrations/add_format_column.sql
```

## Need Help?

Check [`migrations/README.md`](migrations/README.md) for detailed troubleshooting.

---

**After Fix**: Your application should start normally! 🎉

# Resume Editor API - Deployment Guide

## 🚀 Quick Deploy to Render (Free Tier)

### Step 1: Push to GitHub

```bash
git add .
git commit -m "Add database and deployment support"
git push origin main
```

### Step 2: Deploy on Render

1. Go to [render.com](https://render.com) and sign up/login
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Name**: `resume-editor-api`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: `Free`

### Step 3: Add PostgreSQL Database (Free)

1. In Render Dashboard → "New +" → "PostgreSQL"
2. **Name**: `resume-editor-db`
3. **Database**: `resume_editor`
4. **User**: `resume_user`
5. **Instance Type**: `Free`
6. Click "Create Database"
7. Copy the **Internal Database URL**

### Step 4: Configure Environment Variables

In your Web Service → "Environment" tab, add:

```
DATABASE_URL=<paste-internal-database-url-from-step-3>
OPENAI_API_KEY=<your-openai-api-key>
PASSWORD_SALT=your_random_salt_string_here
```

### Step 5: Deploy!

Click "Manual Deploy" → "Deploy latest commit"

Your API will be live at: `https://resume-editor-api.onrender.com`

---

## 📋 API Endpoints

### Authentication

#### Register New User
```bash
curl -X POST https://your-app.onrender.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"user_id": "testuser", "password": "securepass123"}'
```

#### Login
```bash
curl -X POST https://your-app.onrender.com/api/auth/login \
  -u testuser:securepass123
```

### Resume Generation

#### Start Resume Generation
```bash
curl -X POST https://your-app.onrender.com/api/generate_resume_json \
  -u testuser:securepass123 \
  -H "Content-Type: application/json" \
  -d @resume_request.json
```

#### Check Job Status
```bash
curl https://your-app.onrender.com/api/jobs/{request_id}/status \
  -u testuser:securepass123
```

#### Get Completed Resume JSON
```bash
curl https://your-app.onrender.com/api/jobs/{request_id}/result \
  -u testuser:securepass123
```

#### Download Resume DOCX
```bash
curl https://your-app.onrender.com/api/jobs/{request_id}/download \
  -u testuser:securepass123 \
  -o resume.docx
```

#### Get Job History
```bash
curl https://your-app.onrender.com/api/user/jobs?limit=10 \
  -u testuser:securepass123
```

---

## 🗄️ Database Schema

### Users Table
- `id`: Primary key
- `user_id`: Username (unique)
- `password_hash`: Hashed password
- `created_at`: Account creation timestamp
- `last_login`: Last login timestamp
- `is_active`: Account status

### Resume Jobs Table
- `id`: Primary key
- `user_id`: Foreign key to users
- `request_id`: Unique job identifier
- `company_name`: Target company
- `job_title`: Target position
- `mode`: "complete_jd" or "resume_jd"
- `jd_text`: Job description input
- `resume_input_json`: Original resume data
- `final_resume_json`: Generated resume (stored as JSON)
- `status`: "pending", "processing", "completed", "failed"
- `progress`: 0-100%
- `error_message`: Error details if failed
- `created_at`: Job creation timestamp
- `completed_at`: Completion timestamp

---

## 🔧 Local Development

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="sqlite:///./resume_editor.db"
export OPENAI_API_KEY="your-key-here"

# Run locally
uvicorn app.main:app --reload --port 8000
```

### Test Locally
```bash
# Register user
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "password": "test123"}'

# Health check
curl http://localhost:8000/health
```

---

## 📊 Features

✅ **User Authentication** - Simple username/password auth  
✅ **Job Queue** - Background processing with progress tracking  
✅ **Database Storage** - PostgreSQL for production, SQLite for local  
✅ **On-the-fly DOCX Generation** - No file storage needed  
✅ **Job History** - View past resume generations  
✅ **Error Handling** - Failed jobs tracked with error messages  
✅ **CORS Enabled** - Ready for frontend integration  

---

## 🔒 Security Notes

- Passwords are hashed with PBKDF2-SHA256
- Use HTTPS in production (Render provides free SSL)
- Never commit API keys or passwords
- Rotate PASSWORD_SALT regularly
- Consider rate limiting for production

---

## 💰 Cost

**Render Free Tier:**
- Web Service: 750 hours/month (enough for demos)
- PostgreSQL: 1GB storage, 97 hours/month runtime
- SSL certificate included
- **Total Cost: $0/month**

**Limitations:**
- App spins down after 15 min inactivity (cold start ~30s)
- Database limited to 1GB

**Upgrade Options:**
- Starter ($7/month): Always-on, more resources
- PostgreSQL ($7/month): 10GB storage, always-on

---

## 🎯 Next Steps for Production

1. **Add Rate Limiting**
2. **Implement JWT tokens** (instead of Basic Auth)
3. **Add user email verification**
4. **Set up monitoring** (Sentry, DataDog)
5. **Add resume versioning**
6. **Implement file cleanup** (delete old .docx files)
7. **Add usage analytics**

---

## 🐛 Troubleshooting

**Database connection fails:**
- Check DATABASE_URL is correct
- Ensure PostgreSQL is running
- Verify network access

**Cold starts slow:**
- Upgrade to paid tier for always-on
- Or accept 30s startup on free tier

**Out of memory:**
- Reduce worker threads
- Upgrade instance type

---

## 📞 Support

For issues, check logs in Render Dashboard → Logs tab

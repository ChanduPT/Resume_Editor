# 🚀 Deployment Checklist

## Pre-Deployment

- [ ] All code changes committed to Git
- [ ] `.env` file NOT committed (check `.gitignore`)
- [ ] OpenAI API key ready
- [ ] GitHub repository created and code pushed

## Render Setup

### Step 1: Create PostgreSQL Database
- [ ] Sign up/login to Render.com
- [ ] Click "New +" → "PostgreSQL"
- [ ] Name: `resume-editor-db`
- [ ] Database: `resume_editor`  
- [ ] User: `resume_user`
- [ ] Region: Choose closest to your users
- [ ] Plan: **Free**
- [ ] Click "Create Database"
- [ ] **COPY** the "Internal Database URL" (starts with `postgres://`)

### Step 2: Create Web Service
- [ ] Click "New +" → "Web Service"
- [ ] Connect your GitHub repository
- [ ] Select the repository: `resume_editor_v1.1`
- [ ] Name: `resume-editor-api` (or your preferred name)
- [ ] Region: Same as database
- [ ] Branch: `main` (or your default branch)
- [ ] Root Directory: (leave blank)
- [ ] Environment: **Python 3**
- [ ] Build Command: `pip install -r requirements.txt`
- [ ] Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- [ ] Plan: **Free**

### Step 3: Configure Environment Variables
In your Web Service → "Environment" tab, add:

- [ ] `DATABASE_URL` = `<paste the Internal Database URL from Step 1>`
- [ ] `OPENAI_API_KEY` = `sk-your-actual-openai-key`
- [ ] `PASSWORD_SALT` = `your_random_salt_string_change_this_now`

**Important:** 
- Use the **Internal Database URL**, not the External one
- Change `PASSWORD_SALT` to something random and unique

### Step 4: Deploy
- [ ] Click "Create Web Service"
- [ ] Wait for build to complete (2-3 minutes)
- [ ] Check logs for any errors
- [ ] Note your deployment URL: `https://resume-editor-api.onrender.com`

## Post-Deployment Testing

### Test 1: Health Check
```bash
curl https://your-app.onrender.com/health
```
- [ ] Returns `{"status": "healthy", ...}`

### Test 2: Register User
```bash
curl -X POST https://your-app.onrender.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"user_id": "testuser", "password": "testpass123"}'
```
- [ ] Returns success message

### Test 3: Login
```bash
curl -X POST https://your-app.onrender.com/api/auth/login \
  -u testuser:testpass123
```
- [ ] Returns login successful

### Test 4: Generate Resume
Update `test_api.py` with your deployment URL:
```python
BASE_URL = "https://your-app.onrender.com"
```

Run:
```bash
python3 test_api.py
```
- [ ] All tests pass
- [ ] Resume generates successfully
- [ ] DOCX downloads correctly

## Troubleshooting

### Database Connection Issues
- [ ] Check DATABASE_URL is the **Internal** URL
- [ ] Verify database and web service are in same region
- [ ] Check database is active (not spun down)

### Build Failures
- [ ] Check `requirements.txt` is in root directory
- [ ] Verify all dependencies are listed
- [ ] Check Python version compatibility

### Runtime Errors
- [ ] Check Environment Variables are set correctly
- [ ] View logs in Render Dashboard → Logs tab
- [ ] Verify OPENAI_API_KEY is valid

### Cold Start Issues
- [ ] Expected on free tier after 15 min inactivity
- [ ] First request after wake-up takes ~30 seconds
- [ ] Subsequent requests are fast
- [ ] Upgrade to paid tier ($7/month) for always-on

## Security Checklist

- [ ] `.env` file is in `.gitignore`
- [ ] API keys not committed to Git
- [ ] `PASSWORD_SALT` changed from default
- [ ] HTTPS enabled (automatic on Render)
- [ ] Test with different users to verify isolation

## Optional Enhancements

- [ ] Add custom domain
- [ ] Set up monitoring/alerts
- [ ] Add rate limiting
- [ ] Implement JWT tokens
- [ ] Add email verification
- [ ] Set up CI/CD pipeline
- [ ] Add usage analytics

## Going Live

- [ ] Share API URL with testers
- [ ] Document API endpoints for frontend team
- [ ] Set up error monitoring (Sentry, etc.)
- [ ] Plan for scaling if needed
- [ ] Monitor database storage usage

## Free Tier Limits to Monitor

- **Web Service:**
  - 750 hours/month (enough for demo/testing)
  - Sleeps after 15 min inactivity
  
- **PostgreSQL:**
  - 1GB storage
  - 97 hours/month runtime
  - Auto-sleeps when inactive

**When limits are reached:**
- Upgrade Web Service: $7/month (always-on)
- Upgrade PostgreSQL: $7/month (10GB, always-on)

## Success Criteria

Your deployment is successful when:
- [ ] Health endpoint responds
- [ ] Users can register and login
- [ ] Resumes generate successfully
- [ ] Progress tracking works
- [ ] DOCX files download correctly
- [ ] Job history shows past generations
- [ ] No errors in logs
- [ ] Database persists data across restarts

---

## 🎉 Congratulations!

Once all items are checked, your Resume Editor API is live and ready for public testing!

**Next Steps:**
1. Share the API URL with testers
2. Gather feedback
3. Monitor usage and errors
4. Iterate on features
5. Plan scaling strategy

**Support:**
- Render docs: https://render.com/docs
- Issues: Check logs in Render Dashboard
- Database: Monitor usage in PostgreSQL dashboard

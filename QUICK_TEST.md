# 🚀 Quick Start - Testing Your Resume Builder

## ✅ Server Status: RUNNING
- **URL:** http://localhost:5001/
- **Status:** Healthy ✓
- **Browser:** Should be open now!

---

## 📱 What You Should See Right Now

### **In Your Browser:**

```
┌────────────────────────────────────────────────────────────┐
│  Resume Builder Pro                       🌙 Night  ℹ️ About │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ 📝 Create    │  │ ✏️ Edit      │  │ 📊 My        │   │
│  │    Resume    │  │    Resume    │  │    Dashboard │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
│  ────────────────                                         │
│                                                            │
│  (Resume form with fields should be visible here)         │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## 🎯 3-Minute Test (Do This First!)

### **Step 1: Click "📊 My Dashboard" Tab**
You should see:
```
👋 Welcome to Resume Builder Pro
Login or create an account to track your resume history

[Login]  [Register]
─────────────────

(Forms appear here)
```

### **Step 2: Register Account**
1. Click **"Register"** tab
2. Fill in:
   - Username: `testuser`
   - Password: `test123`
   - Confirm: `test123`
3. Click **"Create Account"**

**✅ Expected:** Green message "Account created! Please login."

### **Step 3: Login**
1. Should auto-switch to Login tab
2. Enter:
   - Username: `testuser`
   - Password: `test123`
3. Click **"Login"**

**✅ Expected:** Dashboard appears with:
```
┌─────────────────────────────────────────┐
│ Welcome, testuser! | Created: Nov 2     │
└─────────────────────────────────────────┘

┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│    0     │ │    0     │ │    0     │ │    20    │
│  Total   │ │  Active  │ │  Today's │ │Remaining │
│ Resumes  │ │   Jobs   │ │ Resumes  │ │  Today   │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
```

### **Step 4: Generate First Resume**
1. You should be on **"📝 Generate New"** panel
2. Fill in:
   ```
   Company: Google
   Job Title: Software Engineer
   Job Description: 
   Looking for a software engineer with Python and React 
   experience. Must have strong problem-solving skills.
   
   Mode: Complete JD
   ```
3. Click **"Generate Resume"**

**✅ Expected:** 
- Switches to "📚 My Resumes" tab
- Job card appears
- Progress bar starts updating
- Active Jobs changes to 1

### **Step 5: Watch Progress**
- Progress bar fills: 5% → 10% → 40% → 60% → 75% → 95% → 100%
- Status: pending → processing → completed
- Takes ~30-60 seconds

**✅ Expected:** 
```
┌─────────────────────────────────────────────────┐
│ Software Engineer              [completed]      │
│ Google                                          │
│ Nov 2, 2025 5:34 PM                            │
│                                                 │
│ [Download DOCX]  [View JSON]                   │
└─────────────────────────────────────────────────┘
```

### **Step 6: Download Resume**
1. Click **"Download DOCX"**
2. File downloads: `resume_xxxxx.docx`
3. Open it in Word/Pages

**✅ Expected:** 
- Formatted resume document
- Tailored to Google Software Engineer role
- Professional layout

---

## 🎬 What's Happening Behind the Scenes?

### **When You Click "Generate Resume":**

```
1. Frontend → POST /api/generate_resume_json
2. Backend → Checks rate limits ✓
3. Backend → Checks quotas ✓
4. Backend → Creates job in database (status: pending)
5. Backend → Starts background task
6. Background Task:
   ├─ Extract JD hints (5%)
   ├─ Score resume (10%)
   ├─ Generate summary (40%)
   ├─ Generate experience (60%)
   ├─ Generate skills (75%)
   ├─ Finalize (95%)
   └─ Complete (100%)
7. Frontend → Polls every 2 seconds
8. Frontend → Updates progress bar
9. Complete → Shows download button
```

---

## 🔍 Check Console for Details

### **Open Browser DevTools:**
1. Press **F12** or **Cmd+Option+I** (Mac)
2. Go to **Console** tab
3. You should see:
   ```
   [Dashboard] User logged in: testuser
   [Dashboard] Generating resume...
   [Dashboard] Request ID: 12345678-...
   [Dashboard] Polling status...
   [Dashboard] Progress: 5%
   [Dashboard] Progress: 10%
   ...
   [Dashboard] Complete!
   ```

### **Check Network Tab:**
1. Go to **Network** tab
2. Generate a resume
3. You should see:
   ```
   POST  /api/generate_resume_json   200
   GET   /api/jobs/xxxxx/status      200  (repeats every 2s)
   GET   /api/jobs/xxxxx/download    200
   ```

---

## 📊 Test All Features Checklist

### **✅ Quick Tests (5 min):**
- [ ] Can see all 3 tabs
- [ ] Can register account
- [ ] Can login
- [ ] Dashboard shows stats
- [ ] Can generate resume
- [ ] Progress updates in real-time
- [ ] Can download DOCX
- [ ] Can view JSON

### **✅ Complete Tests (15 min):**
- [ ] Generate multiple resumes
- [ ] Check history persists
- [ ] Logout and re-login
- [ ] Test Tab 1 (Create Resume - no login)
- [ ] Test Tab 2 (Edit Resume - no login)
- [ ] Test rate limiting (5 req/min)
- [ ] Test concurrent jobs (max 3)
- [ ] Test daily quota display

---

## 🎯 Key URLs to Test

### **Main Site:**
- http://localhost:5001/

### **API Endpoints:**
- http://localhost:5001/health (health check)
- http://localhost:5001/docs (API documentation)
- http://localhost:5001/redoc (Alternative API docs)

### **Try These API Docs:**
1. Open: http://localhost:5001/docs
2. You'll see all endpoints listed
3. Can test them directly from browser!

---

## 🐛 If Something Goes Wrong

### **Can't See Dashboard Tab?**
- Refresh browser (Cmd+R / Ctrl+R)
- Clear cache (Cmd+Shift+R / Ctrl+Shift+R)

### **Login Not Working?**
- Check Console (F12) for errors
- Try different username
- Verify server is running: `curl http://localhost:5001/health`

### **Resume Generation Stuck?**
- Check server terminal for errors
- Verify OpenAI API key in `.env`
- Check `debug_files/` folder for error logs

### **Download Not Working?**
- Check if job status is "completed"
- Try "View JSON" first to verify job finished
- Check browser download settings

---

## 💡 Pro Tips

### **Tip 1: Test Rate Limiting**
Try generating 6 resumes in < 1 minute:
```
1. Generate resume 1 → ✓
2. Generate resume 2 → ✓
3. Generate resume 3 → ✓
4. Generate resume 4 → ✓
5. Generate resume 5 → ✓
6. Generate resume 6 → ✗ "Rate limit exceeded"
```

### **Tip 2: Monitor Database**
```bash
# See all users
sqlite3 resume_editor.db "SELECT * FROM users;"

# See all jobs
sqlite3 resume_editor.db "SELECT request_id, status, company_name FROM resume_jobs;"
```

### **Tip 3: Watch Logs**
```bash
# In terminal where server is running
# You'll see real-time logs of:
# - API calls
# - Job progress
# - Errors (if any)
```

---

## 🎉 Success Indicators

You know it's working when:

✅ **Visual:**
- All 3 tabs visible and switchable
- Dashboard shows stats after login
- Progress bars fill smoothly
- Download button appears when done

✅ **Functional:**
- Can register new account
- Can login successfully
- Resumes generate correctly
- DOCX downloads and opens
- History shows all past jobs

✅ **Technical:**
- Server responds to /health
- Database creates tables
- No errors in console
- Network requests successful

---

## 📱 Your Next Steps

### **Right Now:**
1. ✅ Browser should be open at http://localhost:5001/
2. ✅ Click "📊 My Dashboard"
3. ✅ Register → Login → Generate!

### **After Testing:**
1. Review `TESTING_GUIDE.md` for detailed tests
2. Check `UNIFIED_SITE.md` for architecture
3. See `DEPLOYMENT.md` when ready to deploy

---

## 🚀 **Start Testing NOW!**

**Your browser is already open. Just:**
1. Click **"📊 My Dashboard"** tab
2. Click **"Register"**
3. Create account → Login
4. Fill the form → Click **"Generate Resume"**
5. Watch the magic happen! ✨

**Have fun!** 🎊

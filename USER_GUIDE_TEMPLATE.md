# Resume Template Feature - Quick Guide

## What's New? 🎉

Your resume editor now saves your resume data automatically!

---

## How It Works

### 1️⃣ Save Your Resume
1. Go to **"👁️ View Resume"** tab
2. Fill in your resume details (name, skills, experience, etc.)
3. Click the **"💾 Save My Resume"** button (bottom-right corner)
4. You'll see: "✅ Resume template saved successfully!"

### 2️⃣ Auto-Load on Login
1. Logout and login again
2. Your resume form will automatically fill with saved data
3. You'll see a toast: "✅ Resume template loaded!"

### 3️⃣ Update Your Template
1. Edit any resume fields
2. Click **"💾 Save My Resume"** again
3. Your template is updated!

---

## Where's the Button?

The **"💾 Save My Resume"** button appears:
- ✅ In "View Resume" tab
- ❌ NOT in "Generate Resume" tab
- ❌ NOT in "Dashboard" tab

**Location**: Bottom-right corner, just above the "↑" scroll button

---

## What Gets Saved?

### ✅ Saved to Template
- Your name
- Contact info (phone, email, LinkedIn)
- Skills list
- Work experience (all entries)
- Education (all entries)
- Projects (all entries)
- Certifications (all entries)

### ❌ NOT Saved
- Job descriptions (in Generate Resume tab)
- Company name for resume generation
- Job title for resume generation

**Why?** These change for each resume you generate!

---

## Visual Guide

```
┌─────────────────────────────────────────┐
│  Resume Editor                          │
│  ┌────┐ ┌────┐ ┌────┐                  │
│  │View│ │Gen │ │Dash│  👤 username  🚪 │
│  └────┘ └────┘ └────┘                  │
├─────────────────────────────────────────┤
│                                         │
│  View Resume Tab (Form)                 │
│                                         │
│  Name: [John Doe           ]            │
│  Location: [New York, NY   ]            │
│                                         │
│  📞 Contact Information                 │
│  Phone: [123-456-7890      ]            │
│  Email: [john@example.com  ]            │
│                                         │
│  💼 Skills                              │
│  Skill 1: [Python          ]            │
│  Skill 2: [JavaScript      ]            │
│                                         │
│                                         │
│                                         │
│                                         │
│                             ┌─────────┐ │
│                             │📂 Upload│ │
│                             │💾 Down  │ │
│                             │🧹 Clear │ │
│                             └─────────┘ │
│                             ┌─────────┐ │
│                             │💾 Save  │ │ ← NEW!
│                             │My Resume│ │
│                             └─────────┘ │
│                                    ┌──┐ │
│                                    │↑ │ │
│                                    └──┘ │
└─────────────────────────────────────────┘
```

---

## Tips & Tricks

1. **Save Early, Save Often**
   - Save your template after adding basic info
   - Update whenever you add new skills or experience

2. **One Template Per User**
   - Each user has ONE saved template
   - Clicking save will always update your existing template

3. **It's Just Resume Data**
   - Template = Your personal info
   - Job descriptions = Separate (entered each time)

4. **Quick Start for New Resumes**
   - Login → Form already filled
   - Go to "Generate Resume" tab
   - Paste job description
   - Click generate!

---

## Keyboard Shortcuts

None yet, but you can:
- `Ctrl/Cmd + F` to find fields
- `Tab` to navigate between inputs
- Click button to save (no shortcut needed)

---

## FAQs

**Q: What if I want to start over?**
A: Use the 🧹 Clear All button, then save the empty form (not recommended)

**Q: Can I have multiple templates?**
A: Not yet! Each user has one template. Save your best version.

**Q: Does this save my generated resumes?**
A: No, this saves your TEMPLATE (your info). Generated resumes are in Dashboard.

**Q: What if I don't see the button?**
A: Make sure you're on the "View Resume" tab (first tab)

**Q: Can I download my template?**
A: Yes! Use the "💾 Download JSON" button in View Resume tab

**Q: Will this work on mobile?**
A: Yes! The button is positioned for both desktop and mobile

---

## Developer Notes

**API Endpoints:**
- `POST /api/user/resume-template` - Save/update
- `GET /api/user/resume-template` - Retrieve

**Database:**
- Table: `user_resume_templates`
- Stores: JSON of resume data
- Auto-updates: `updated_at` timestamp

**Frontend:**
- Button: `#saveTemplateBtn`
- Save function: `saveResumeTemplate()`
- Load function: `loadResumeTemplate()`
- Auto-loads: On `handleMainLogin()`

---

**Need Help?** Check TEMPLATE_FEATURE.md for technical details!

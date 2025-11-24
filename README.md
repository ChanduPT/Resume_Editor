# Resume Builder Pro

An AI-powered resume builder that tailors your resume to specific job descriptions using LLM technology (Google Gemini/OpenAI).

## 🎉 What's New (v2.0)

**Major Feature Updates:**
- 📄 **Dual Resume Formats** - Choose between Classic (traditional) and Modern (contemporary) layouts
- ✏️ **Interactive Edit Mode** - Click-to-edit any section of generated resumes
- 🔧 **Advanced Skills Management** - Edit skill category names AND values, add/remove categories
- 👁️ **View Modal System** - Preview resumes and job descriptions before downloading
- 🔐 **User Authentication** - Secure multi-user system with isolated resume histories
- 📊 **Enhanced Dashboard** - Search, filter, and manage all your resumes in one place
- ✅ **Three-Layer Validation** - Frontend, backend, and document-level validation prevents errors
- 📥 **Dual Downloads** - Download both resume DOCX and original job description
- 🎨 **UI/UX Improvements** - Modern design with smooth animations and theme toggle
- 💾 **Database Persistence** - All edits save permanently to database
- ❓ **Built-in Help System** - Comprehensive tutorial accessible anytime

## 🚀 Quick Deploy (Free)

**Deploy to Render.com in 5 minutes - $0/month**

📖 **Full Guide:** [`DEPLOY_FREE.md`](DEPLOY_FREE.md)  
⚡ **Quick Reference:** [`FREE_TIER_SUMMARY.md`](FREE_TIER_SUMMARY.md)

**Free Tier Capacity:** 1-2 concurrent users, 2 jobs per user

## ✨ Features

### � User Management
- **User Authentication** - Secure login and registration system
- **Multi-User Support** - Each user has their own isolated resume history
- **Session Management** - Persistent login with secure token-based authentication
- **User Dashboard** - Personal workspace to manage all your resumes

### 🎯 AI-Powered Resume Generation
- **Dual AI Support** - Works with both OpenAI GPT and Google Gemini models
- **Two Generation Modes**:
  - **Complete JD Mode**: Generate entire resume from job description alone
  - **Resume + JD Mode**: Apply intelligent edits to your existing resume based on job requirements
- **Smart Matching** - AI analyzes job descriptions and tailors content automatically
- **Keyword Optimization** - Extracts and incorporates relevant skills and technologies
- **ATS-Friendly** - Generates resumes optimized for Applicant Tracking Systems

### 📊 Dashboard & Job Tracking
- **Comprehensive Dashboard** - View all your generated resumes in one place
- **Search & Filter** - Find resumes by company name, job title, or status
- **Status Tracking** - Real-time status updates (Processing, Completed, Failed)
- **Job History** - Complete history of all resume generations with timestamps
- **Concurrent Processing** - Generate up to 2 resumes simultaneously (queues additional requests)

### 🔍 Job Search Integration
- **JSearch API Integration** - Real job data from multiple sources via OpenWebNinja
- **Multi-Source Scraping** - Workday, Greenhouse, Lever job board support
- **Smart Fallback** - Sample jobs for development when API unavailable
- **Intelligent Caching** - 24-hour cache reduces API calls and improves performance
- **Location & Date Filtering** - Remote jobs, specific locations, recent postings
- **Per-User Limits** - Maximum 2 active jobs per user to ensure fair resource allocation

### ✏️ Advanced Editing Features
- **Live Resume Preview** - View generated resumes in a modal before downloading
- **Edit Mode** - Click-to-edit any section of your generated resume
- **Technical Skills Management**:
  - Edit skill category names (keys)
  - Edit skills within categories (values)
  - Add new skill categories on-the-fly
  - Remove unwanted categories
- **Experience Bullet Points** - Edit all job descriptions and achievements
- **Inline Updates** - All changes sync to your database instantly
- **Version Control** - Save and retrieve different versions via JSON export

### 📄 Import/Export & Downloads
- **Dual Resume Formats**:
  - **Classic Format** - Traditional Times New Roman with underlined headers (best for corporate, finance, law)
  - **Modern Format** - Clean Calibri with bold headers (best for tech, startups, creative roles)
- **JSON Import/Export** - Save your resume data for reuse across multiple applications
- **DOCX Generation** - Professional Word documents with proper formatting
- **Dual Downloads** - Download both resume and original job description
- **Auto-Naming** - Files named as `CompanyName_YYYYMMDD_HHMMSS.docx`
- **Batch Operations** - Manage multiple resumes efficiently

### 🎨 User Experience
- **Modern UI** - Clean, intuitive interface with smooth animations
- **Light/Dark Theme** - Toggle between themes for comfortable viewing
- **Responsive Design** - Works seamlessly on desktop, tablet, and mobile
- **Real-time Notifications** - Toast notifications for all operations
- **Progress Indicators** - Visual feedback during generation (30-90 seconds)
- **Form Validation** - Client and server-side validation prevents errors
- **Help System** - Built-in tutorial accessible via ❓ Help button

### 🔒 Security & Validation
- **Input Validation** - Three-layer validation (frontend, backend, document generation)
- **Required Fields Checking** - Ensures all critical data is present before generation
- **Email Validation** - Proper email format checking
- **Character Limits** - Minimum 50 characters for summary and job descriptions
- **SQL Injection Prevention** - Parameterized queries with SQLAlchemy ORM
- **XSS Protection** - Sanitized inputs and outputs

## How It Works

### Architecture

```
┌─────────────────┐
│  Frontend (UI)  │  ← Single-page HTML application
└────────┬────────┘
         │
         │ HTTP POST /api/generate_resume_json
         ▼
┌─────────────────┐
│  FastAPI Server │  ← Async API with ThreadPoolExecutor (4 workers)
└────────┬────────┘
         │
         ├─► Normalize & Parse Resume Text
         ├─► Generate JD Hints (LLM)
         ├─► Score & Plan Edits (LLM)
         ├─► Rewrite Sections (LLM)
         ├─► Balance Bullets (6-8 per role)
         ├─► Organize Skills by Category
         └─► Create DOCX File
                ▼
         ┌──────────────┐
         │  Output File │  CompanyName_20251026_123456.docx
         └──────────────┘
```

### Processing Pipeline

1. **Input Collection**:
   - Resume data (name, contact, summary, skills, experience, education)
   - Job description and company name
   - Generation mode (Complete JD or Resume + JD)

2. **Text Processing**:
   - Convert resume JSON to plain text
   - Normalize whitespace and formatting
   - Split into sections (Summary, Skills, Experience, etc.)

3. **AI Analysis**:
   - Extract keywords and requirements from job description
   - Score resume against job requirements
   - Generate section-specific edit recommendations

4. **Content Generation**:
   - **Complete JD Mode**: Uses `GENERATE_FROM_JD_PROMPT` to create content from scratch
   - **Resume + JD Mode**: Uses `APPLY_EDITS_PROMPT` to apply targeted edits
   - Rewrite Summary, Skills, and Experience sections
   - Balance bullet points (6-8 per role)
   - Organize skills into categories

5. **Document Creation**:
   - Parse rewritten text into structured JSON
   - Generate formatted DOCX file with proper styling
   - Save to `generated_resumes/` folder

## Installation

### Prerequisites

- Python 3.12 or higher
- pip3 package manager

### Step 1: Clone or Download

```bash
cd ~/Downloads
# Your project should be in: resume_editor_v1.1/
```

### Step 2: Install Dependencies

```bash
cd Resume_Editor
pip3 install -r requirements.txt
```

**Required packages**:
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `python-docx` - Word document generation
- `python-dotenv` - Environment variable management
- `openai` - OpenAI API client (if using GPT)
- `google-generativeai` - Gemini API client (if using Gemini)

### Step 3: Configure API Keys

Create a `.env` file in the project root (already created for you):

**For Google Gemini** (Recommended):
```bash
LLM_PROVIDER=GEMINI
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-2.5-flash
```

**For OpenAI GPT**:
```bash
LLM_PROVIDER=OPENAI
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini
```

## Running the Application

### Start the Backend Server

```bash
cd resume_editor_v1.1
uvicorn app.main:app --reload --port 5001
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:5001 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using WatchFiles
INFO:     Application startup complete.
```

### Open the Frontend

1. Open `index.html` in your web browser
2. Or use a local server:
   ```bash
   python3 -m http.server 8000
   ```
   Then visit: `http://localhost:8000`

## 📖 How to Use the Application

### First Time Setup

1. **Create an Account**:
   - Open the application in your browser
   - Click "Register" on the login screen
   - Create a username and password
   - Login with your credentials

2. **Access Help Anytime**:
   - Click the **❓ Help** button in the header for a complete tutorial
   - The help modal provides step-by-step guidance

### Step-by-Step Guide

#### 1️⃣ Choose Your Generation Mode

**📝 Complete JD Mode** (Generate from Job Description):
- Best when: Starting from scratch or don't have an existing resume
- AI creates: Entire resume based on job description
- Requirements: Only job description, company name, and title

**🔄 Resume + JD Mode** (Tailor Existing Resume):
- Best when: You have an existing resume to optimize
- AI applies: Targeted edits to match job requirements
- Requirements: Your resume data + job description
- **Recommended**: Produces better, more personalized results

#### 2️⃣ Fill in Job Description Details

1. **Company Name**: Enter the company you're applying to
2. **Job Title**: Enter the exact position title
3. **Job Description**: Paste the complete job posting including:
   - Responsibilities and requirements
   - Required skills and technologies
   - Qualifications and experience levels
   - **Minimum**: 50 characters (full job descriptions work best)

#### 3️⃣ Add Your Resume Data (Resume + JD Mode Only)

If using **Resume + JD Mode**, fill in these sections:

**Basic Information**:
- Name, email, phone, LinkedIn, location
- Required fields must be complete

**Professional Summary**:
- Write a brief overview of your experience (minimum 50 characters)
- Include key achievements and focus areas

**Technical Skills**:
- Add categories (e.g., "Programming Languages", "Frameworks", "Tools")
- Enter comma-separated skills for each category
- Click "+ Add Skill" for more categories

**Experience**:
- Company name, role title, employment period
- Add bullet points describing achievements (use action verbs)
- Quantify results when possible (e.g., "Increased sales by 30%")
- Click "+ Add Bullet" for more points
- Click "+ Add Experience" for additional roles

**Education**:
- Degree, institution, graduation year
- Click "+ Add Education" for multiple degrees

**Optional Sections**:
- **Projects**: Showcase personal or professional projects
- **Certifications**: Add relevant certifications

**💾 Save Your Data**:
- Click **Download JSON** to save your resume data
- Click **Upload JSON** to load previously saved data
- Reuse your data for multiple job applications

#### 4️⃣ Generate Your Resume

1. Click **🚀 Generate Resume**
2. Validation runs automatically (you'll see errors if fields are missing)
3. Processing takes **30-90 seconds**
4. Track progress with:
   - ✅ Green success notification
   - 📊 Real-time dashboard updates
   - 🔔 Status badges (Processing → Completed)

**Concurrent Processing**:
- Generate up to **2 resumes simultaneously**
- Additional requests queue automatically
- Each user can have max 2 active jobs

#### 5️⃣ View and Download Results

Access your generated resumes from the **Dashboard**:

**View Resume**:
1. Click the **👁️ View** button in the kebab menu (⋮)
2. Preview the complete formatted resume
3. Review all sections before downloading

**Edit Mode** (POWERFUL NEW FEATURE):
1. Click **✏️ Edit** button in the view modal
2. **Any text becomes editable** - just click it!
3. Advanced editing capabilities:
   - ✅ **Personal Info**: Name, email, phone, LinkedIn, location
   - ✅ **Summary**: Professional overview and career highlights
   - ✅ **Experience**: Job titles, companies, dates, bullet points
   - ✅ **Education**: Degrees, institutions, years
   - ✅ **Projects**: Project names, descriptions, technologies
   - ✅ **Certifications**: Certification names and dates
   
4. **Technical Skills - Advanced Management**:
   - 📝 **Edit Category Names**: Click category names (e.g., "Programming Languages") to rename
   - 💡 **Edit Skill Values**: Click skill lists to add/remove/modify individual skills
   - ➕ **Add New Categories**: Click "Add Category" button to create new skill groups
   - 🗑️ **Remove Categories**: Delete unwanted skill categories with trash icon
   - 🎯 **Example**: Change "Languages" to "Programming Languages" or add "Cloud Platforms"
   
5. Click **💾 Save Changes** to persist all edits to database
6. Click **Cancel** to exit edit mode without saving
7. ⚠️ **Note**: Saved changes are permanent and affect all future downloads

**Download Options**:
- Click **📥 Download Resume** for the professionally formatted DOCX file
- Click **📋 Download Job Description** to save the original JD as text
- Files auto-named: `CompanyName_YYYYMMDD_HHMMSS.docx`
- Download from view modal OR dashboard kebab menu (⋮)

#### 6️⃣ Dashboard Features

**Search & Filter System**:
- 🔍 **Search Bar**: Find resumes by company name or job title (real-time filtering)
- 📊 **Status Filter**: View All, Completed, Processing, or Failed jobs
- 📅 **Automatic Sorting**: Most recent resumes appear first
- 🔄 **Live Updates**: Dashboard refreshes automatically when jobs complete

**Kebab Menu Actions** (⋮):
Each resume entry has a kebab menu with these options:
- 👁️ **View Resume**: Open interactive preview modal with edit capability
- 👁️ **View Job Description**: Review the original job posting you submitted
- 📥 **Download Resume**: Direct download of DOCX file
- 📋 **Download JD**: Download job description as text file
- 🗑️ **Delete**: Permanently remove entry from your history

**Status Indicators**:
- 🟢 **Completed**: Resume ready - view, edit, and download available
- 🟡 **Processing**: AI is generating your resume (30-90 seconds)
- 🔴 **Failed**: Error occurred - hover/click for error details
- ⏳ **Queued**: Waiting for available slot (when 2 jobs already running)

**Job Information Display**:
- Company name and job title prominently displayed
- Generation timestamp (e.g., "Nov 9, 2025 2:30 PM")
- Generation mode badge (Complete JD or Resume + JD)
- Visual status badge with color coding

---

## 🚀 Quick Reference - Common Tasks

### Generating Your First Resume

```
1. Login/Register → 2. Choose "Resume + JD" mode → 3. Fill resume data
→ 4. Paste job description → 5. Click "Generate" → 6. Wait 30-90s
→ 7. View/Edit in dashboard → 8. Download DOCX
```

### Editing a Generated Resume

```
Dashboard → Click ⋮ → "View Resume" → Click "Edit" button
→ Click any text to edit → Modify as needed → Click "Save Changes"
```

### Managing Technical Skills

```
View Resume → Edit Mode → Click category name to rename
→ Click skills to modify → Use "Add Category" for new groups
→ Click trash icon to remove categories → Save Changes
```

### Reusing Resume Data

```
Build Resume → Fill all fields → Click "Download JSON"
→ Save file locally → Next application: Click "Upload JSON"
→ Modify as needed → Generate new tailored resume
```

### Finding Old Resumes

```
Dashboard → Use search bar (company/title) → Or filter by status
→ Click ⋮ menu → Select desired action (View/Download/Delete)
```

### Troubleshooting Failed Generation

```
Check validation errors → Ensure 50+ char for summary/JD
→ Verify API keys in .env → Check server is running
→ Try regenerating → Check browser console for errors
```

---

### 💡 Pro Tips

**Content Quality:**
- ✅ **Fill all required fields**: Summary and job description need 50+ characters
- 🎯 **Use action verbs**: Led, Developed, Achieved, Implemented, Increased, Spearheaded
- 📊 **Quantify achievements**: Include numbers, percentages, impact metrics (e.g., "Reduced costs by 25%")
- � **Be specific**: Paste complete job descriptions for better AI matching
- 💼 **Resume + JD Mode recommended**: Produces more personalized results with existing resume

**Using Features:**
- �🔄 **Try multiple times**: Each generation varies slightly due to AI - regenerate if needed
- ✏️ **Powerful edit mode**: Click any text to edit, rename skill categories, add new sections
- 🔧 **Technical skills management**: Edit both category names (keys) AND skill values
- 👁️ **Preview first**: Use view mode to review before downloading DOCX
- 💾 **Save best versions**: Export winning resumes as JSON to reuse structure
- 📋 **Track applications**: Use dashboard search to remember which companies you've applied to

**Optimization:**
- ⚡ **Concurrent processing**: Generate 2 resumes simultaneously for different jobs
- � **Customize after generation**: Add niche skills and technologies mentioned in JD
- 🗑️ **Clean up**: Delete old/test resumes to keep dashboard organized
- 🌙 **Theme preference**: Toggle light/dark mode for comfortable extended use

### ⚠️ Common Issues

**Validation Errors**:
- Check all required fields are filled
- Ensure summary and JD are 50+ characters
- Verify email format is valid
- Add at least one experience and education entry (Resume + JD mode)

**Generation Fails**:
- Check API keys are configured correctly in `.env`
- Verify server is running (`uvicorn` command)
- Check browser console for detailed errors
- Try regenerating - sometimes API rate limits apply

**Download Issues**:
- Ensure resume has "Completed" status
- Check browser popup blocker settings
- Try viewing first, then download from view modal

5. **Download Result**:
   - Resume saves to `generated_resumes/CompanyName_YYYYMMDD_HHMMSS.docx`

## Project Structure

```
resume_editor_v1.1/
├── app/
│   ├── main.py              # FastAPI server & API endpoints
│   ├── create_resume.py     # DOCX generation logic
│   ├── utils.py             # LLM calls, parsing, text processing
│   └── prompts.py           # LLM prompt templates
├── generated_resumes/       # Output folder for DOCX files
├── debug_files/             # Debug logs and intermediate files
├── index.html               # Frontend single-page application
├── requirements.txt         # Python dependencies
├── .env                     # API keys and configuration
└── README.md               # This file
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | AI provider (`GEMINI` or `OPENAI`) | `OPENAI` |
| `GEMINI_API_KEY` | Google Gemini API key | - |
| `GEMINI_MODEL` | Gemini model name | `gemini-2.5-flash` |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4o-mini` |
| `JSEARCH_API_KEY` | JSearch API key from OpenWebNinja | - |
| `JWT_SECRET` | JWT token secret for authentication | `resume_jwt_secret_2025` |
| `DATABASE_URL` | PostgreSQL database connection string | `sqlite:///./resume_editor.db` |

#### 🔑 Getting JSearch API Key (Free Tier Available)

1. **Sign up for OpenWebNinja**: Go to [api.openwebninja.com](https://api.openwebninja.com)
2. **Get JSearch API Access**: Navigate to the JSearch API section
3. **Subscribe to Free Tier**: 1,000 requests/month free
4. **Get API Key**: Copy your x-api-key
5. **Set Environment Variable**: `JSEARCH_API_KEY=your_key_here`

**With JSearch API configured:**
- ✅ Real job data from multiple job sources
- ✅ Up-to-date job postings from major companies  
- ✅ Salary ranges, employment types, remote options
- ✅ Professional job descriptions and requirements

**Without JSearch API:**
- 🔄 Falls back to web scraping (limited success)
- 🎭 Demo job data for development/testing

### Concurrency Settings

The backend uses `ThreadPoolExecutor` with **4 workers** for concurrent processing.

To change this, edit `app/main.py`:
```python
executor = ThreadPoolExecutor(max_workers=4)  # Change to desired number
```

## API Endpoints

### POST `/api/generate_resume_json`

Generate a tailored resume from resume data and job description.

**Request Body**:
```json
{
  "resume_data": {
    "name": "John Doe",
    "contact": "john@example.com | 123-456-7890",
    "summary": "Professional summary...",
    "technical_skills": {
      "Programming Languages": "Python, JavaScript",
      "Databases": "PostgreSQL, MongoDB"
    },
    "experience": [...],
    "education": [...]
  },
  "job_description_data": {
    "company_name": "Microsoft",
    "job_description": "Full job posting text..."
  },
  "mode": "complete_jd"  // or "resume_jd"
}
```

**Response**:
```json
{
  "result": "Resume generated successfully",
  "file_name": "Microsoft_20251026_123456.docx"
}
```

## Features Explained

### Concurrent Request Tracking

The UI tracks multiple simultaneous resume generations:

- **Processing Banner**: Shows all active requests with company names
- **Real-time Counter**: "Processing 3 resumes..."
- **Status Indicators**:
  - 🔄 Spinner = Processing
  - ✓ Green = Completed
  - ✗ Red = Failed
- **Auto-cleanup**: Completed items fade out after 5 seconds

### Generation Modes

#### Complete JD Mode
- Uses `GENERATE_FROM_JD_PROMPT`
- Creates content from scratch based on job requirements
- Best for: Applying to very different roles or industries

#### Resume + JD Mode
- Uses `APPLY_EDITS_PROMPT`
- Applies targeted edits to preserve your original content
- Best for: Similar roles where you want to keep your achievements

### Bullet Point Balancing

Automatically ensures each role has 6-8 bullet points:
- Too many bullets → Condense most impactful ones
- Too few bullets → Expand on existing achievements

### Skills Organization

Groups skills into standard categories:
- Programming Languages
- Data & Business Intelligence
- Databases & Big Data
- Cloud Technologies
- Tools & Frameworks
- Business & Professional Skills
- Certifications & Training

## Troubleshooting

### Port Already in Use

```bash
# Kill process on port 5001
lsof -ti:5001 | xargs kill -9

# Restart server
uvicorn app.main:app --reload --port 5001
```

### API Key Errors

```
RuntimeError: GEMINI_API_KEY is not set
```

**Solution**: Check your `.env` file contains the correct API key:
```bash
cat .env  # Verify contents
```

### Module Not Found

```bash
pip3 install -r requirements.txt  # Reinstall dependencies
```

### DOCX Not Generated

Check the `generated_resumes/` folder exists and has write permissions:
```bash
ls -la generated_resumes/
chmod 755 generated_resumes/
```

## Development

### Logging

Logs are saved to:
- Console output (terminal)
- `debug_files/app.log`

Log levels can be changed in `app/main.py`:
```python
logging.basicConfig(level=logging.DEBUG)  # Change to INFO, WARNING, etc.
```

### Debug Files

Intermediate processing files are saved to `debug_files/`:
- Job descriptions
- Section rewrites
- Parsed JSON structures

Uncomment `_save_debug_file()` calls in `app/main.py` to enable.

## Performance

- **Concurrent Requests**: 4 simultaneous resume generations
- **Average Processing Time**: 30-60 seconds per resume (depends on LLM API)
- **Rate Limits**: Constrained by your LLM provider's API limits

## Security Notes

⚠️ **Important**: Never commit `.env` file to version control!

Add to `.gitignore`:
```
.env
*.docx
debug_files/
__pycache__/
generated_resumes/
```

## License

This project is for educational and personal use.

## Support

For issues or questions:
1. Check terminal logs for error messages
2. Verify API keys are set correctly
3. Ensure all dependencies are installed
4. Check `debug_files/app.log` for detailed errors

---

Built with ❤️ using FastAPI, OpenAI/Gemini, and modern web technologies.

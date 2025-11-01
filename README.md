# Resume Builder Pro

An AI-powered resume builder that tailors your resume to specific job descriptions using LLM technology (OpenAI GPT or Google Gemini).

## Features

- 📝 **Smart Resume Editing** - Build and edit resumes with an intuitive web interface
- 🎯 **Job Description Matching** - Automatically tailor your resume to match job requirements
- 🤖 **Dual AI Support** - Works with both OpenAI GPT and Google Gemini models
- 🔄 **Two Generation Modes**:
  - **Complete JD**: Generate resume entirely from job description
  - **Resume + JD**: Apply targeted edits to existing resume based on job description
- 📊 **Concurrent Processing** - Handle up to 4 simultaneous resume generations
- 🎨 **Modern UI** - Clean, responsive design with light/dark theme support
- 💾 **Import/Export** - Upload and download resume data as JSON
- 📄 **DOCX Output** - Generate professional Word documents ready for submission
- 🔔 **Real-time Tracking** - Visual notifications for multiple concurrent resume generations

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
cd resume_editor_v1.1
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

### Using the Application

#### Resume Tab (Build Your Resume)

1. **Basic Information**:
   - Enter your name, contact info, and professional summary

2. **Technical Skills**:
   - Add skill categories (e.g., "Programming Languages", "Databases")
   - Enter comma-separated values for each category
   - Click "+ Add Skill" for more categories

3. **Experience**:
   - Add company, role, and period
   - Add bullet points for achievements
   - Click "+ Add Bullet" for more points
   - Click "+ Add Experience" for more roles

4. **Education**:
   - Add degree, institution, and year
   - Click "+ Add Education" for multiple entries

5. **Save/Load**:
   - Use 💾 **Download JSON** to save your resume data
   - Use 📂 **Upload JSON** to load previously saved data

#### Edit Resume Tab (Generate Tailored Resume)

1. **Enter Company Name**:
   - Type the company you're applying to

2. **Choose Generation Mode**:
   - ⭐ **Complete JD** (default): Generate resume entirely from job description
   - 🔧 **Resume + JD**: Apply edits to existing resume based on JD

3. **Paste Job Description**:
   - Copy the entire job posting
   - Paste into the text area

4. **Generate Resume**:
   - Click "Generate Resume Based on JD"
   - Watch the processing banner track progress
   - Multiple requests can run simultaneously (up to 4)

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

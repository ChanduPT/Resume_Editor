# Resume Processing Detailed Logging

## Overview

Every resume processing request now creates **two detailed log files**:

1. **Summary Log** (`summary_TIMESTAMP_REQUESTID.log`) - Readable, high-level overview
2. **Debug Log** (`debug_TIMESTAMP_REQUESTID.log`) - Full detailed debugging information

## Log Files Location

All logs are stored in: `/Users/chanduprasadreddypotukanuma/Downloads/resume_editor_v1.1/logs/`

## What's Logged

### Summary Log (Readable Format)
- Request metadata (mode, company, job title)
- Input resume data (summary, skills, experience)
- JD analysis results (keywords extracted)
- Step-by-step processing progress
- **Input vs Output comparisons** for each section
- Verification that data is preserved (in resume_jd mode)

### Debug Log (Full Details)
- All API calls and responses
- LLM prompts and completions
- Error stack traces
- Performance metrics
- Raw JSON data

## Viewing Logs

### Quick View (Latest Summary Log)
```bash
./view_logs.sh
```

### View Specific Log
```bash
cat logs/summary_20251111_080240_test_resume_jd_001.log
```

### View Latest Debug Log
```bash
ls -t logs/debug_*.log | head -1 | xargs cat
```

### Search Logs
```bash
# Find all logs for a specific request ID
grep -l "req_12345" logs/*.log

# Search for errors
grep "ERROR\|⚠️\|❌" logs/summary_*.log
```

## Log Format

### Section Headers
```
================================================================================
  RESUME PROCESSING START - Request ID: req_xxx
================================================================================
```

### Subsections
```
--- REQUEST METADATA ---
--- INPUT RESUME DATA ---
--- JD ANALYSIS RESULTS ---
```

### Data Logging
```
Name: John Doe
Summary: Experienced Software Engineer...
Technical Skills:
{
  "Languages": ["Python", "Java"],
  "Frameworks": ["Django", "React"]
}
```

### Comparisons (resume_jd mode)
```
📊 SUMMARY COMPARISON:
----------------------------------------
INPUT:  Experienced Software Engineer...
OUTPUT: Experienced Software Engineer...
✅ UNCHANGED (as expected)
----------------------------------------
```

## Key Indicators

- ✅ **Green checkmark** - Data preserved successfully
- ⚠️  **Warning** - Unexpected modification
- ❌ **Error** - Processing failed
- 📊 **Chart** - Comparison or statistics
- 📝 **Note** - Log file location
- 🔍 **Magnifying glass** - Verification step

## Debugging resume_jd Mode

When using `resume_jd` mode, the logs will clearly show:

1. **Input data** captured at start
2. **Mode detection**: "RESUME_JD MODE - PRESERVING ORIGINAL"
3. **Processing decision**: "Returning original summary unchanged"
4. **Output verification**: Comparison showing INPUT === OUTPUT
5. **Final verification**: "✅ UNCHANGED (as expected)"

If summary or skills are being modified incorrectly, the logs will show:
- `⚠️  Summary was modified (unexpected!)`
- The exact INPUT vs OUTPUT values
- Where in the code the modification happened

## Example Log Flow (resume_jd mode)

```
RESUME PROCESSING START
  Mode: resume_jd
  
INPUT RESUME DATA
  Summary: "Experienced engineer..."
  Skills: {"Python": [...], "AWS": [...]}
  
SUMMARY GENERATION (resume_jd mode)
  ✓ PRESERVING ORIGINAL SUMMARY
  Input: "Experienced engineer..."
  Output: "Experienced engineer..."
  ✅ Summary preserved successfully
  
SKILLS GENERATION (resume_jd mode)
  ✓ PRESERVING ORIGINAL SKILLS
  Input: 3 categories
  Output: 3 categories
  ✅ Skills preserved successfully
  
FINAL OUTPUT COMPARISON
  📊 SUMMARY: ✅ UNCHANGED
  📊 SKILLS: ✅ UNCHANGED
  📊 EXPERIENCE: ℹ️  Intentionally modified
  
PROCESSING COMPLETE ✅
```

## Troubleshooting

### No logs being created
- Check if `logs/` directory exists
- Verify logging is not disabled in configuration

### Logs too large
- Old logs are not automatically deleted
- Manually clean up: `rm logs/*_$(date -v-7d +%Y%m%d)*.log` (older than 7 days)

### Can't find specific request
- Use request_id from the frontend
- Search: `grep -r "request_id_here" logs/`

## Performance Impact

- Log files are written asynchronously
- Minimal impact on processing time (~0.1s overhead)
- Summary log: ~5-10 KB per request
- Debug log: ~10-20 KB per request

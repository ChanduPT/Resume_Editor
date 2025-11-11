#!/bin/bash
# View the latest resume processing logs

LOG_DIR="/Users/chanduprasadreddypotukanuma/Downloads/resume_editor_v1.1/logs"

echo "=================================================================================="
echo "RESUME PROCESSING LOGS"
echo "=================================================================================="
echo ""

# Find the latest summary log
LATEST_SUMMARY=$(ls -t "$LOG_DIR"/summary_*.log 2>/dev/null | head -1)
LATEST_DEBUG=$(ls -t "$LOG_DIR"/debug_*.log 2>/dev/null | head -1)

if [ -z "$LATEST_SUMMARY" ]; then
    echo "❌ No log files found in $LOG_DIR"
    exit 1
fi

echo "📁 Latest logs:"
echo "   Summary: $(basename "$LATEST_SUMMARY")"
echo "   Debug:   $(basename "$LATEST_DEBUG")"
echo ""
echo "=================================================================================="
echo "SUMMARY LOG (Readable Format)"
echo "=================================================================================="
echo ""

cat "$LATEST_SUMMARY"

echo ""
echo ""
echo "=================================================================================="
echo "📝 To view the detailed debug log, run:"
echo "   cat \"$LATEST_DEBUG\""
echo "=================================================================================="

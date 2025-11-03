#!/bin/bash
# Quick test script to verify UI integration

echo "🧪 Testing Resume Editor UI Integration..."
echo ""

# Check if server is running
echo "1️⃣ Checking if server is running..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "   ✅ Server is running!"
else
    echo "   ❌ Server is NOT running. Start it with:"
    echo "      python -m uvicorn app.main:app --reload"
    exit 1
fi

echo ""
echo "2️⃣ Checking dashboard availability..."
if curl -s http://localhost:8000/ | grep -q "Resume Editor"; then
    echo "   ✅ Dashboard is accessible at http://localhost:8000/"
else
    echo "   ⚠️  Dashboard might not be loading correctly"
fi

echo ""
echo "3️⃣ Checking old editor availability..."
if curl -s http://localhost:8000/old-editor | grep -q "Resume Builder Pro"; then
    echo "   ✅ Old editor is accessible at http://localhost:8000/old-editor"
else
    echo "   ⚠️  Old editor might not be loading correctly"
fi

echo ""
echo "4️⃣ Testing API endpoints..."

# Test health endpoint
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo "   ✅ Health endpoint working"
else
    echo "   ❌ Health endpoint failed"
fi

echo ""
echo "5️⃣ Testing database connection..."
# Try to register a test user (will fail if user exists, but shows DB is working)
response=$(curl -s -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"user_id":"testuser","password":"testpass"}' 2>&1)

if echo "$response" | grep -q "created\|already exists"; then
    echo "   ✅ Database is working!"
else
    echo "   ⚠️  Database might have issues"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎯 Integration Test Complete!"
echo ""
echo "📊 Summary:"
echo "   • Backend API:     http://localhost:8000/docs"
echo "   • New Dashboard:   http://localhost:8000/"
echo "   • Old Editor:      http://localhost:8000/old-editor"
echo ""
echo "🚀 Next Steps:"
echo "   1. Open browser to http://localhost:8000/"
echo "   2. Register a new account"
echo "   3. Generate a resume"
echo "   4. Check job history"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

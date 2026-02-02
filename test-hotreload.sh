#!/bin/bash
set -e

echo "🧪 Testing Hot Reload Setup"
echo ""

# Check if containers are running
echo "1. Checking if containers are running..."
if ! docker compose ps | grep -q "aibi-backend.*Up"; then
    echo "❌ Backend container is not running"
    echo "   Run: docker compose up -d"
    exit 1
fi

if ! docker compose ps | grep -q "aibi-frontend.*Up"; then
    echo "❌ Frontend container is not running"
    echo "   Run: docker compose up -d"
    exit 1
fi

echo "✅ All containers running"
echo ""

# Check backend file mounting
echo "2. Checking backend file mounting..."
if docker compose exec -T backend test -f /app/app.py; then
    echo "✅ Backend app.py is accessible in container"
else
    echo "❌ Backend app.py not found in container"
    exit 1
fi

# Check frontend file mounting
echo "3. Checking frontend file mounting..."
if docker compose exec -T frontend test -d /app/src; then
    echo "✅ Frontend src directory is accessible in container"
else
    echo "❌ Frontend src directory not found in container"
    exit 1
fi

echo ""
echo "✨ Hot reload setup verified!"
echo ""
echo "📝 To test hot reload:"
echo ""
echo "   Frontend (instant HMR):"
echo "   1. Open http://localhost:3000 in browser"
echo "   2. Edit frontend/src/App.jsx"
echo "   3. Save → Browser updates instantly"
echo ""
echo "   Backend (auto-restart):"
echo "   1. Watch logs: docker compose logs -f backend"
echo "   2. Edit backend/app.py"
echo "   3. Save → Flask restarts in ~2-3 seconds"
echo ""

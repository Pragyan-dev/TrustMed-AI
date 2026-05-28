#!/bin/bash
# TrustMed AI - Development Server
# Runs both FastAPI backend and Next.js frontend

echo "🩺 Starting TrustMed AI..."

# Check if we're in the right directory
if [ ! -f "api/main.py" ]; then
    echo "❌ Error: Run this script from the TrustMed-AI root directory"
    exit 1
fi

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}
trap cleanup INT TERM

# Start backend
echo "🔧 Starting FastAPI backend on port 8000..."
if [ -x ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
else
    PYTHON_BIN="python3"
fi

if [ "${DEV_RELOAD:-0}" = "1" ]; then
    $PYTHON_BIN -m uvicorn api.main:app --reload --port 8000 --reload-dir api --reload-dir src &
else
    $PYTHON_BIN -m uvicorn api.main:app --port 8000 &
fi
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start frontend
echo "🎨 Starting Next.js frontend on port 5173..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ TrustMed AI is running!"
echo ""
echo "   Frontend: http://localhost:5173"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all servers"

# Wait for either process to exit
wait

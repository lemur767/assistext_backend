#!/bin/bash
set -e

echo "🚀 Starting AssisText services..."

# Navigate to app directory
cd /opt/assistext_backend

# Activate virtual environment
source venv/bin/activate

# Set environment variables
export FLASK_APP=wsgi.py
export FLASK_ENV=production

# Ensure Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "Starting Redis..."
    sudo systemctl start redis-server
    sleep 2
fi

# Kill any existing processes
pkill -f "gunicorn.*wsgi:app" || true
pkill -f "celery.*wsgi" || true
sleep 2

# Start backend
echo "Starting backend..."
nohup gunicorn --bind 127.0.0.1:8000 --workers 2 --worker-class sync --timeout 120 wsgi:app > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend started with PID: $BACKEND_PID"

# Wait for backend to start
sleep 5

# Test backend is running
if curl -s http://localhost:8000/api/health > /dev/null; then
    echo "✅ Backend is responding"
else
    echo "❌ Backend failed to start"
    exit 1
fi

# Start Celery
#echo "Starting Celery worker..."
#nohup celery -A wsgi.celery worker --loglevel=info --concurrency=2 --pool=solo > logs/celery.log 2>&1 &
#CELERY_PID=$!
#echo "Celery started with PID: $CELERY_PID"

# Save PIDs
#echo $BACKEND_PID > pids/backend.pid
#echo $CELERY_PID > pids/celery.pid

# Wait and check if Celery is still running
#sleep 5
#if ps -p $CELERY_PID > /dev/null; then
 #   echo "✅ Celery is running successfully"
#else
 #   echo "❌ Celery failed to start, check logs/celery.log"
#fi

echo ""
echo "🎉 AssisText started!"
echo "📊 Status:"
echo "   Backend: http://localhost:5000/api/health"
echo "   Logs: tail -f logs/backend.log logs/celery.log"
echo "   Stop: ./stop_assistext.sh"

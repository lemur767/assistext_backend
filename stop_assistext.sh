#!/bin/bash
echo "🛑 Stopping AssisText..."

# Stop using PID files
if [ -f pids/backend.pid ]; then
    kill $(cat pids/backend.pid) 2>/dev/null || true
    rm pids/backend.pid
fi

if [ -f pids/celery.pid ]; then
    kill $(cat pids/celery.pid) 2>/dev/null || true
    rm pids/celery.pid
fi

# Kill any remaining processes
pkill -f "gunicorn.*wsgi:app" || true
pkill -f "celery.*wsgi" || true

echo "✅ AssisText stopped"

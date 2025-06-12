#!/bin/bash

echo "🏥 AssisText Health Check"
echo "========================"

# Check Redis
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis: Working"
else
    echo "❌ Redis: Failed"
fi

# Check Database
if psql "postgresql://app_user:AssisText2025SecureDB@localhost:5432/assistext_prod" -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ Database: Working"
else
    echo "❌ Database: Failed"
fi

# Check Backend
if curl -s http://localhost:5000/api/health > /dev/null 2>&1; then
    echo "✅ Backend: Working"
else
    echo "❌ Backend: Failed"
fi

# Check processes
if pgrep -f "gunicorn.*wsgi:app" > /dev/null; then
    echo "✅ Gunicorn: Running"
else
    echo "❌ Gunicorn: Not running"
fi

if pgrep -f "celery.*worker" > /dev/null; then
    echo "✅ Celery: Running"
else
    echo "❌ Celery: Not running"
fi

echo ""
echo "🔗 Service URLs:"
echo "   Health: http://localhost:5000/api/health"
echo "   Backend: http://localhost:5000/"
echo ""
echo "📊 Process Status:"
ps aux | grep -E "(gunicorn|celery)" | grep -v grep || echo "   No processes found"

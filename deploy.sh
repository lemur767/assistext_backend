#!/bin/bash

# AssisText Automated Deployment Script
# Customized for assitext.ca configuration

set -e  # Exit on any error

PROJECT_DIR="/opt/assistext_backend"
VENV_DIR="$PROJECT_DIR/assistext_env"
LOG_FILE="$PROJECT_DIR/deployment.log"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== ASSITEXT DEPLOYMENT STARTED ==="

# Change to project directory
cd "$PROJECT_DIR"

# Create backup of current version
log "Creating backup..."
if [ -d "app_backup" ]; then
    rm -rf app_backup_old
    mv app_backup app_backup_old
fi
cp -r app app_backup

# Pull latest code from origin/main
log "Pulling latest code from origin/main..."
git fetch origin
git reset --hard origin/main

# Activate virtual environment
log "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Install/update dependencies
log "Installing dependencies..."
pip install -r requirements.txt

# Run database migrations
log "Running database migrations..."
export FLASK_APP=wsgi:application
flask db upgrade

# Test the application before restarting services
log "Testing application..."
python -c "
import sys
sys.path.insert(0, '/opt/assistext_backend')
try:
    from app import create_app
    app = create_app()
    print('✅ App imports successfully')
except Exception as e:
    print(f'❌ App import failed: {e}')
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    log "❌ Application test failed - Rolling back"
    rm -rf app
    mv app_backup app
    exit 1
fi

# Restart services with zero downtime
log "Restarting services..."

# Graceful restart of Gunicorn (zero downtime)
if sudo systemctl is-active --quiet assistext-gunicorn; then
    sudo systemctl reload assistext-gunicorn
    log "✅ Gunicorn reloaded"
else
    sudo systemctl start assistext-gunicorn
    log "✅ Gunicorn started"
fi

# Restart Celery workers
sudo systemctl restart assistext-celery
log "✅ Celery worker restarted"

sudo systemctl restart assistext-celerybeat
log "✅ Celery beat restarted"

# Wait for services to start
sleep 5

# Health check
log "Performing health check..."
if curl -f -s https://backend.assitext.ca/health > /dev/null; then
    log "✅ Backend health check passed"
elif curl -f -s http://localhost:5000/health > /dev/null; then
    log "✅ Local health check passed"
else
    log "❌ Health check failed - Rolling back"
    # Rollback
    rm -rf app
    mv app_backup app
    sudo systemctl reload assistext-gunicorn
    exit 1
fi

# Cleanup old backups (keep last 3)
log "Cleaning up old backups..."
ls -dt app_backup* 2>/dev/null | tail -n +4 | xargs -r rm -rf

log "=== ASSITEXT DEPLOYMENT COMPLETED SUCCESSFULLY ==="

# Optional: Send notification
# curl -X POST -H 'Content-type: application/json' \
#     --data '{"text":"🚀 AssisText deployed successfully!"}' \
#     YOUR_SLACK_WEBHOOK_URL

exit 0

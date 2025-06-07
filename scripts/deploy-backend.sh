#!/bin/bash
# AssisText Backend Deployment Script
# Run as admin user

set -e

REPO_URL="https://github.com/yourusername/assistext-backend.git"
APP_DIR="/opt/assistext-backend"
LLM_SERVER_IP="10.0.0.102"  # Update with actual LLM server IP

cd $APP_DIR

# Pull latest code
if [ -d ".git" ]; then
    git pull origin main
else
    echo "No git repository found. Please clone your repository first:"
    echo "git clone $REPO_URL $APP_DIR"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python3.11 -m venv venv
fi

# Activate virtual environment and install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create production environment file
cat > .env.production << 'EOF_ENV'
# Flask Configuration
FLASK_ENV=production
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
JWT_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')

# Database Configuration
DATABASE_URL=postgresql://app_user:AssisText2025!SecureDB@localhost:5432/assistext_prod
DEV_DATABASE_URL=postgresql://app_user:AssisText2025!SecureDB@localhost:5432/assistext_dev

# Redis Configuration
CELERY_BROKER_URL=redis://:AssisText2025!Redis@localhost:6379/0
CELERY_RESULT_BACKEND=redis://:AssisText2025!Redis@localhost:6379/0

# Twilio Configuration (update with your credentials)
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
VERIFY_TWILIO_SIGNATURE=True

# AI Configuration (LLM server)
EOF_ENV
echo "OPENAI_API_BASE=http://$LLM_SERVER_IP:8080/v1" >> .env.production
cat >> .env.production << 'EOF_ENV'
OPENAI_API_KEY=local-api-key
OPENAI_MODEL=llama2

# Stripe Configuration (update with your credentials)
STRIPE_SECRET_KEY=your_stripe_secret_key
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret

# Security Settings
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax
PERMANENT_SESSION_LIFETIME=3600

# Rate Limiting
RATELIMIT_STORAGE_URL=redis://:AssisText2025!Redis@localhost:6379/1
EOF_ENV

# Run database migrations
export FLASK_APP=wsgi.py
export FLASK_ENV=production
flask db upgrade

# Create Gunicorn configuration
cat > gunicorn.conf.py << 'EOF_GUNICORN'
bind = "127.0.0.1:5000"
workers = 4
worker_class = "eventlet"
worker_connections = 1000
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
user = "admin"
group = "admin"
EOF_GUNICORN

echo "Backend deployment preparation completed!"
echo "Next: Configure supervisor to run the application"

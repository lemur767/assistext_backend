#!/bin/bash

# =============================================================================
# AssisText Backend Complete Setup Script
# =============================================================================
# This script sets up the complete backend infrastructure for AssisText
# including PostgreSQL, Redis, Flask application, and all dependencies
# 
# Configuration:
# - Database: assistext_prod
# - DB User: app_user  
# - Password: Assistext2025Secure (for both DB and Redis)
# - Backend Port: 8000
# - System User: admin (existing)
# - Working Directory: /opt/assistext_backend/
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration Variables
DB_NAME="assistext_prod"
DB_USER="app_user"
DB_PASSWORD="Assistext2025Secure"
REDIS_PASSWORD="Assistext2025Secure"
BACKEND_PORT="8000"
SYSTEM_USER="admin"
APP_DIR="/opt/assistext_backend"
LOG_DIR="/var/log/assistext"

# Print functions
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root"
        exit 1
    fi
}

# =============================================================================
# SYSTEM PREPARATION
# =============================================================================

install_system_dependencies() {
    print_status "Updating system packages..."
    apt update && apt upgrade -y
    
    print_status "Installing system dependencies..."
    apt install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        postgresql \
        postgresql-contrib \
        postgresql-client \
        redis-server \
        nginx \
        supervisor \
        curl \
        wget \
        git \
        build-essential \
        libpq-dev \
        pkg-config \
        libffi-dev \
        libssl-dev \
        unzip
    
    print_success "System dependencies installed"
}

# =============================================================================
# POSTGRESQL SETUP
# =============================================================================

setup_postgresql() {
    print_status "Configuring PostgreSQL..."
    
    # Start and enable PostgreSQL
    systemctl start postgresql
    systemctl enable postgresql
    
    # Create database user and database
    sudo -u postgres psql << EOF
-- Create user if not exists
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_USER}') THEN
        CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
    END IF;
END
\$\$;

-- Create database if not exists
SELECT 'CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DB_NAME}')\\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
ALTER USER ${DB_USER} CREATEDB;

-- Enable required extensions
\\c ${DB_NAME}
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

\\q
EOF
    
    # Configure PostgreSQL for network connections
    POSTGRES_VERSION=$(sudo -u postgres psql -t -c "SELECT version();" | grep -oP '\d+\.\d+' | head -1)
    PG_CONFIG_DIR="/etc/postgresql/16/main"
    
    # Update postgresql.conf
    sed -i "s/#listen_addresses = 'localhost'/listen_addresses = 'localhost'/" "${PG_CONFIG_DIR}/postgresql.conf"
    
    # Update pg_hba.conf for local connections
    if ! grep -q "local   ${DB_NAME}   ${DB_USER}" "${PG_CONFIG_DIR}/pg_hba.conf"; then
        echo "local   ${DB_NAME}   ${DB_USER}   md5" >> "${PG_CONFIG_DIR}/pg_hba.conf"
    fi
    
    # Restart PostgreSQL
    systemctl restart postgresql
    
    print_success "PostgreSQL configured successfully"
    print_status "Database: ${DB_NAME}, User: ${DB_USER}"
}

# =============================================================================
# REDIS SETUP
# =============================================================================

setup_redis() {
    print_status "Configuring Redis..."
    
    # Stop Redis to configure it
    systemctl stop redis-server
    
    # Backup original config
    cp /etc/redis/redis.conf /etc/redis/redis.conf.backup
    
    # Configure Redis with password
    cat > /etc/redis/redis.conf << EOF
# Redis Configuration for AssisText
bind 127.0.0.1
port 6379
timeout 0
tcp-keepalive 300

# Security
requirepass ${REDIS_PASSWORD}
protected-mode yes

# Memory and Persistence
maxmemory 256mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000

# Logging
loglevel notice
logfile /var/log/redis/redis-server.log

# Database
databases 16
dbfilename dump.rdb
dir /var/lib/redis
EOF
    
    # Set proper permissions
    chown redis:redis /etc/redis/redis.conf
    chmod 640 /etc/redis/redis.conf
    
    # Start and enable Redis
    systemctl start redis-server
    systemctl enable redis-server
    
    # Test Redis connection
    redis-cli -a "${REDIS_PASSWORD}" ping > /dev/null
    
    print_success "Redis configured successfully with password authentication"
}

# =============================================================================
# APPLICATION DIRECTORY SETUP
# =============================================================================

#setup_application_directories() {
 #   print_status "Setting up application directories..."
    
    # Create main application directory
  #  mkdir -p "${APP_DIR}"
   # mkdir -p "${LOG_DIR}"
   # mkdir -p "/var/run/assistext"
    
    # Create directory structure
  #  mkdir -p "${APP_DIR}/app"
  #  mkdir -p "${APP_DIR}/app/models"
  #  mkdir -p "${APP_DIR}/app/api"
   # mkdir -p "${APP_DIR}/app/services"
   # mkdir -p "${APP_DIR}/app/utils"
   # mkdir -p "${APP_DIR}/migrations"
  #  mkdir -p "${APP_DIR}/tests"
  #  mkdir -p "${APP_DIR}/logs"
  #  mkdir -p "${APP_DIR}/config"
    
    # Set ownership to admin user
  #  chown -R "${SYSTEM_USER}:${SYSTEM_USER}" "${APP_DIR}"
   # chown -R "${SYSTEM_USER}:${SYSTEM_USER}" "${LOG_DIR}"
  #  chown -R "${SYSTEM_USER}:${SYSTEM_USER}" "/var/run/assistext"
    
   # print_success "Application directories created"
#}

# =============================================================================
# PYTHON VIRTUAL ENVIRONMENT
# =============================================================================

setup_python_environment() {
    print_status "Setting up Python virtual environment..."
    
    # Switch to admin user for Python setup
    sudo -u "${SYSTEM_USER}" bash << EOF
cd "${APP_DIR}"

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install requirements
cat > requirements.txt << 'REQ_EOF'
# Core Flask and API Framework
Flask==2.3.3
Flask-RESTful==0.3.10
Flask-SQLAlchemy==3.1.1
Flask-JWT-Extended==4.5.3
Flask-Mail==0.9.1
Flask-Migrate==4.0.5
Flask-CORS==4.0.0

# Database and ORM
SQLAlchemy==2.0.23
psycopg2-binary==2.9.9
alembic==1.12.1

# SignalWire RELAY SDK
signalwire

# Authentication and Security
Werkzeug==2.3.7
PyJWT==2.8.0
bcrypt==4.1.2
cryptography

# Caching and Background Tasks
redis==5.0.1
celery==5.3.4

# HTTP Requests and API
requests==2.31.0
urllib3==2.1.0

# Data Validation and Serialization
marshmallow==3.20.1
marshmallow-sqlalchemy==0.29.0

# Rate Limiting
Flask-Limiter==3.5.0

# Logging and Monitoring
structlog==23.2.0
python-json-logger==2.0.7

# Environment and Configuration
python-dotenv==1.0.0
click==8.1.7

# WSGI Server for Production
gunicorn==21.2.0
gevent==23.9.1

# Development and Testing
pytest==7.4.3
pytest-flask==1.3.0
factory-boy==3.3.0
REQ_EOF

pip install -r requirements.txt
EOF
    
    print_success "Python environment configured"
}

# =============================================================================
# APPLICATION FILES CREATION
# =============================================================================

create_application_files() {
    print_status "Creating application files..."
    
    # Create main application factory
    cat > "${APP_DIR}/app/__init__.py" << 'EOF'
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_restful import Api
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import redis
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
jwt = JWTManager()
mail = Mail()

def create_app(config_name='production'):
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Load configuration
    if config_name == 'production':
        app.config.from_object('config.ProductionConfig')
    else:
        app.config.from_object('config.DevelopmentConfig')
    
    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)
    
    # Enable CORS
    CORS(app, origins=["https://www.assitext.ca", "https://assitext.ca"])
    
    # Rate limiting
    limiter = Limiter(
        app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri=app.config['REDIS_URL']
    )
    
    # Register API routes
    api = Api(app)
    from app.api.auth import register_auth_routes
    register_auth_routes(api, limiter)
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'service': 'assistext-backend'}, 200
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    return app
EOF

    # Create configuration file
    cat > "${APP_DIR}/config.py" << EOF
import os
from datetime import timedelta

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'eGJheGYyeGZmbHgxNng5NXhjYXhiM3hkZnhlNnhiOHhiOXg5N3g4ZXhmNUJwU3gxMw==')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'xbaxf2xfflx16x95xcaxb3xdfxe6xb5!x1excaxd6x15Cxd7x97x08xb9x97x8exf5BpSx13')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # SignalWire Configuration
    SIGNALWIRE_SPACE_URL = os.environ.get('SIGNALWIRE_SPACE_URL')
    SIGNALWIRE_PROJECT_ID = os.environ.get('SIGNALWIRE_PROJECT_ID')
    SIGNALWIRE_AUTH_TOKEN = os.environ.get('SIGNALWIRE_AUTH_TOKEN')
    
    # Application
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:${BACKEND_PORT}')

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'postgresql://${DB_USER}:${DB_PASSWORD}@localhost/${DB_NAME}'
    REDIS_URL = 'redis://localhost:6379/0'
    
class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = 'postgresql://${DB_USER}:${DB_PASSWORD}@localhost/${DB_NAME}'
    REDIS_URL = 'redis://:${REDIS_PASSWORD}@localhost:6379/0'
    
    # Email Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@assistext.ca')
EOF

 
    cat > "${APP_DIR}/app/api/auth.py" << 'EOF'
from flask import request, jsonify, current_app
from flask_restful import Resource
from flask_jwt_extended import create_access_token, create_refresh_token
from app import db
from app.models.user import User
from app.models.profile import Profile
from marshmallow import Schema, fields, validate, ValidationError
from datetime import datetime, timedelta
import logging
import uuid
from signalwire.rest import Client as SignalWireClient

logger = logging.getLogger(__name__)

class UserRegistrationSchema(Schema):
    """Schema for user registration validation"""
    username = fields.Str(required=True, validate=validate.Length(min=3, max=80))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8))
    confirm_password = fields.Str(required=True)
    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    personal_phone = fields.Str(allow_none=True, validate=validate.Length(max=20))

class RegistrationAPI(Resource):
    """Handle user registration endpoint"""
    
    def post(self):
        try:
            schema = UserRegistrationSchema()
            data = schema.load(request.json)
            
            # Validate passwords match
            if data['password'] != data['confirm_password']:
                return {'error': 'Passwords do not match'}, 400
            
            # Check if user exists
            existing_user = User.query.filter(
                (User.username == data['username']) | 
                (User.email == data['email'])
            ).first()
            
            if existing_user:
                return {'error': 'User already exists'}, 409
            
            # Create user
            user = User(
                username=data['username'],
                email=data['email'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                personal_phone=data.get('personal_phone')
            )
            user.set_password(data['password'])
            
            db.session.add(user)
            db.session.commit()
            
            # Generate tokens
            access_token = create_access_token(identity=user.id)
            refresh_token = create_refresh_token(identity=user.id)
            
            return {
                'success': True,
                'message': 'User registered successfully',
                'user': user.to_dict(),
                'access_token': access_token,
                'refresh_token': refresh_token
            }, 201
            
        except ValidationError as e:
            return {'error': 'Validation failed', 'details': e.messages}, 400
        except Exception as e:
            db.session.rollback()
            logger.error(f"Registration error: {str(e)}")
            return {'error': 'Registration failed'}, 500

class PhoneNumberSearchAPI(Resource):
    """Handle phone number search"""
    
    def post(self):
        try:
            data = request.json
            city = data.get('city', 'toronto')
            
            # Mock phone numbers for testing
            mock_numbers = [
                {
                    'phone_number': '+14165551001',
                    'formatted_number': '(416) 555-1001',
                    'locality': city.title(),
                    'region': 'ON',
                    'area_code': '416',
                    'setup_cost': '$1.00',
                    'monthly_cost': '$1.00',
                    'capabilities': {'sms': True, 'voice': True, 'mms': True}
                },
                {
                    'phone_number': '+14165551002',
                    'formatted_number': '(416) 555-1002',
                    'locality': city.title(),
                    'region': 'ON',
                    'area_code': '416',
                    'setup_cost': '$1.00',
                    'monthly_cost': '$1.00',
                    'capabilities': {'sms': True, 'voice': True, 'mms': True}
                }
            ]
            
            return {
                'success': True,
                'city': city,
                'available_numbers': mock_numbers,
                'count': len(mock_numbers)
            }, 200
            
        except Exception as e:
            logger.error(f"Phone search error: {str(e)}")
            return {'error': 'Phone number search failed'}, 500

class CompleteSignupAPI(Resource):
    """Handle complete signup with profile creation"""
    
    def post(self):
        try:
            data = request.json
            
            # Create user
            user = User(
                username=data['username'],
                email=data['email'],
                first_name=data['firstName'],
                last_name=data['lastName'],
                personal_phone=data.get('personalPhone'),
                timezone=data.get('timezone', 'America/Toronto')
            )
            user.set_password(data['password'])
            
            db.session.add(user)
            db.session.flush()
            
            # Create profile
            profile = Profile(
                user_id=user.id,
                name=data['profileName'],
                description=data.get('profileDescription'),
                phone_number=data['selectedPhoneNumber'],
                preferred_city=data.get('preferredCity', 'toronto')
            )
            
            db.session.add(profile)
            db.session.commit()
            
            # Generate tokens
            access_token = create_access_token(identity=user.id)
            refresh_token = create_refresh_token(identity=user.id)
            
            return {
                'success': True,
                'message': 'Account created successfully',
                'user': user.to_dict(),
                'profile': profile.to_dict(),
                'access_token': access_token,
                'refresh_token': refresh_token
            }, 201
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Complete signup error: {str(e)}")
            return {'error': 'Registration failed'}, 500

def register_auth_routes(api, limiter):
    """Register authentication routes with rate limiting"""
    
    # Apply rate limiting
    RegistrationAPI.decorators = [limiter.limit("5 per minute")]
    PhoneNumberSearchAPI.decorators = [limiter.limit("10 per minute")]
    CompleteSignupAPI.decorators = [limiter.limit("3 per minute")]
    
    # Register routes
    api.add_resource(RegistrationAPI, '/api/auth/register')
    api.add_resource(PhoneNumberSearchAPI, '/api/signup/search-numbers')
    api.add_resource(CompleteSignupAPI, '/api/signup/complete-signup')
EOF

     # Create WSGI entry point
    cat > "${APP_DIR}/wsgi.py" << 'EOF'
from app import create_app

application = create_app('production')

if __name__ == "__main__":
    application.run()
EOF

    # Create environment file
    cat > "${APP_DIR}/.env" << EOF
# Flask Configuration
FLASK_APP=wsgi.py
FLASK_ENV=production
SECRET_KEY=eGJheGYyeGZmbHgxNng5NXhjYXhiM3hkZnhlNnhiOHhiOXg5N3g4ZXhmNUJwU3gxMw==
BASE_URL=http://localhost:${BACKEND_PORT}

# Database Configuration
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@localhost/${DB_NAME}

# JWT Configuration
JWT_SECRET_KEY=xbaxf2xfflx16x95xcaxb3xdfxe6xb5!x1excaxd6x15Cxd7x97x08xb9x97x8exf5BpSx13

# Redis Configuration
REDIS_URL=redis://:${REDIS_PASSWORD}@localhost:6379/0

# SignalWire Configuration (Add your credentials)
SIGNALWIRE_SPACE_URL=assitext.signalwire.com
SIGNALWIRE_PROJECT_ID=de26db73-cf95-4570-9d3a-bb44c08eb70e
SIGNALWIRE_AUTH_TOKEN=PTd97f3d390058b8d5cd9b1e00a176ef79e0f314b3548f5e42

# Email Configuration (Optional)
# MAIL_SERVER=smtp.gmail.com
# MAIL_PORT=587
# MAIL_USE_TLS=true
# MAIL_USERNAME=your-email@gmail.com
# MAIL_PASSWORD=your-app-password
# MAIL_DEFAULT_SENDER=noreply@assistext.ca
EOF

    # Set proper ownership
    chown -R "${SYSTEM_USER}:${SYSTEM_USER}" "${APP_DIR}"
    
    print_success "Application files created"
}
# =============================================================================
# DATABASE SCHEMA INITIALIZATION
# =============================================================================

fix_limiter_configuration() {
    print_status "Checking Flask-Limiter configuration..."
    
    # Check if there's a Limiter configuration issue and fix it
    if grep -q "Limiter(" "${APP_DIR}/app/__init__.py"; then
        print_status "Found Limiter configuration, checking for common issues..."
        
        # Create a backup
        cp "${APP_DIR}/app/__init__.py" "${APP_DIR}/app/__init__.py.backup"
        
        # Fix common Limiter configuration issues
        sudo -u "${SYSTEM_USER}" python3 << 'EOF'
import re

# Read the file
with open('/opt/assistext_backend/app/__init__.py', 'r') as f:
    content = f.read()

# Common Flask-Limiter patterns that might cause issues
patterns_to_fix = [
    # Fix multiple key_func arguments
    (r'Limiter\(\s*app,\s*key_func=get_remote_address,\s*key_func=', 'Limiter(\n        key_func='),
    # Fix deprecated storage_uri usage
    (r'storage_uri=', 'storage_uri='),
    # Fix app parameter placement
    (r'Limiter\(\s*app,\s*key_func=get_remote_address,', 'Limiter(\n        key_func=get_remote_address,'),
]

modified = False
for pattern, replacement in patterns_to_fix:
    if re.search(pattern, content):
        content = re.sub(pattern, replacement, content)
        modified = True

# If we have a problematic Limiter configuration, replace it with a working one
if 'TypeError: Limiter.__init__()' in content or modified:
    limiter_pattern = r'limiter = Limiter\([^)]+\)'
    working_limiter = '''limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["200 per day", "50 per hour"],
        storage_uri=app.config.get('REDIS_URL', 'memory://')
    )'''
    
    if re.search(limiter_pattern, content):
        content = re.sub(limiter_pattern, working_limiter, content, flags=re.DOTALL)
        modified = True

if modified:
    with open('/opt/assistext_backend/app/__init__.py', 'w') as f:
        f.write(content)
    print("Fixed Flask-Limiter configuration")
else:
    print("No Flask-Limiter issues found")
EOF
    fi
    
    print_success "Flask-Limiter configuration checked"
}

initialize_database_schema() {
    print_status "Initializing database schema..."
    
    # Run as admin user
    sudo -u "${SYSTEM_USER}" bash << EOF
cd "${APP_DIR}"
source venv/bin/activate

# Load environment variables
export \$(cat .env | grep -v '^#' | xargs)

# Try to initialize the database tables with better error handling
python3 << 'PYTHON_EOF'
import sys
import os
sys.path.append('.')

try:
    # Try importing the app
    from app import create_app, db
    
    print("Creating Flask app...")
    app = create_app()
    
    print("Initializing database tables...")
    with app.app_context():
        db.create_all()
        print("Database tables created successfully")
        
except ImportError as e:
    print(f"Import error: {e}")
    print("This might be due to missing dependencies or app structure differences")
    sys.exit(1)
    
except Exception as e:
    print(f"Error during database initialization: {e}")
    print("Attempting to create tables directly with SQLAlchemy...")
    
    try:
        # Alternative approach using direct SQLAlchemy
        from sqlalchemy import create_engine, text
        import os
        
        db_url = os.environ.get('DATABASE_URL')
        if db_url:
            engine = create_engine(db_url)
            with engine.connect() as conn:
                # Test connection
                result = conn.execute(text("SELECT 1"))
                print("Database connection successful")
                print("You may need to run database migrations manually")
        else:
            print("DATABASE_URL not found in environment")
            
    except Exception as e2:
        print(f"Alternative database setup also failed: {e2}")
        print("Please check your database configuration and try manual setup")
PYTHON_EOF

EOF
    
    print_success "Database schema initialization completed"
}


# =============================================================================
# SYSTEMD SERVICE CONFIGURATION
# =============================================================================

create_systemd_services() {
    print_status "Creating systemd services..."
    
    # Create main application service
    cat > /etc/systemd/system/assistext-backend.service << EOF
[Unit]
Description=AssisText Backend Flask Application
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
Type=simple
User=${SYSTEM_USER}
Group=${SYSTEM_USER}
WorkingDirectory=${APP_DIR}
Environment=PATH=${APP_DIR}/venv/bin
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/venv/bin/gunicorn --bind 0.0.0.0:${BACKEND_PORT} --workers 4 --worker-class gevent --timeout 120 --access-logfile ${LOG_DIR}/access.log --error-logfile ${LOG_DIR}/error.log wsgi:application
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=10
StandardOutput=append:${LOG_DIR}/app.log
StandardError=append:${LOG_DIR}/app-error.log

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd and enable services
    systemctl daemon-reload
    systemctl enable assistext-backend.service
    
    print_success "Systemd services created and enabled"
}

# =============================================================================
# NGINX CONFIGURATION
# =============================================================================

configure_nginx() {
    print_status "Configuring Nginx reverse proxy..."
    
    # Create nginx configuration
    cat > /etc/nginx/sites-available/assistext-backend << EOF
server {
    listen 80;
    server_name localhost;
    
    # Rate limiting
    limit_req_zone \$binary_remote_addr zone=api:10m rate=10r/s;
    
    location / {
        # CORS headers
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS, PUT, DELETE' always;
        add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization' always;
        
        # Handle preflight requests
        if (\$request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' '*';
            add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS, PUT, DELETE';
            add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization';
            add_header 'Access-Control-Max-Age' 1728000;
            add_header 'Content-Type' 'text/plain; charset=utf-8';
            add_header 'Content-Length' 0;
            return 204;
        }
        
        # Proxy to Flask application
        proxy_pass http://127.0.0.1:${BACKEND_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Rate limiting
        limit_req zone=api burst=20 nodelay;
    }
    
    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:${BACKEND_PORT}/health;
        access_log off;
    }
}
EOF

    # Enable the site
    ln -sf /etc/nginx/sites-available/assistext-backend /etc/nginx/sites-enabled/
    
    # Remove default site if it exists
    rm -f /etc/nginx/sites-enabled/default
    
    # Test nginx configuration
    nginx -t
    
    # Start and enable nginx
    systemctl enable nginx
    systemctl restart nginx
    
    print_success "Nginx configured and started"
}

# =============================================================================
# FIREWALL CONFIGURATION
# =============================================================================

configure_firewall() {
    print_status "Configuring firewall..."
    
    # Install ufw if not present
    apt install -y ufw
    
    # Reset firewall rules
    ufw --force reset
    
    # Default policies
    ufw default deny incoming
    ufw default allow outgoing
    
    # Allow SSH
    ufw allow ssh
    
    # Allow HTTP and HTTPS
    ufw allow 80/tcp
    ufw allow 443/tcp
    
    # Allow backend port from localhost only
    ufw allow from 127.0.0.1 to any port ${BACKEND_PORT}
    
    # Enable firewall
    ufw --force enable
    
    print_success "Firewall configured"
}

# =============================================================================
# TESTING AND VALIDATION
# =============================================================================

test_installation() {
    print_status "Testing installation..."
    
    # Test database connection
    sudo -u postgres psql -d "${DB_NAME}" -c "SELECT version();" > /dev/null
    print_success "Database connection: OK"
    
    # Test Redis connection
    redis-cli -a "${REDIS_PASSWORD}" ping | grep -q "PONG"
    print_success "Redis connection: OK"
    
    # Start the backend service
    systemctl start assistext-backend.service
    sleep 5
    
    # Test backend health endpoint
    if curl -s http://localhost:${BACKEND_PORT}/health | grep -q "healthy"; then
        print_success "Backend health check: OK"
    else
        print_warning "Backend health check: Failed (check logs)"
    fi
    
    # Test through nginx
    if curl -s http://localhost/health | grep -q "healthy"; then
        print_success "Nginx proxy: OK"
    else
        print_warning "Nginx proxy: Failed"
    fi
}

# =============================================================================
# LOGGING AND MONITORING SETUP
# =============================================================================

setup_logging() {
    print_status "Setting up logging and monitoring..."
    
    # Create log rotation configuration
    cat > /etc/logrotate.d/assistext << EOF
${LOG_DIR}/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    copytruncate
    su ${SYSTEM_USER} ${SYSTEM_USER}
}
EOF

    # Create monitoring script
    cat > "${APP_DIR}/monitor.py" << 'EOF'
#!/usr/bin/env python3
import psutil
import requests
import json
from datetime import datetime

def check_system_health():
    """Check system health and log metrics"""
    metrics = {
        'timestamp': datetime.now().isoformat(),
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent,
        'backend_status': 'unknown'
    }
    
    # Check backend health
    try:
        response = requests.get('http://localhost:8000/health', timeout=5)
        if response.status_code == 200:
            metrics['backend_status'] = 'healthy'
        else:
            metrics['backend_status'] = 'unhealthy'
    except:
        metrics['backend_status'] = 'down'
    
    # Log metrics
    with open('/var/log/assistext/system-metrics.log', 'a') as f:
        f.write(json.dumps(metrics) + '\n')
    
    print(f"System Health: CPU {metrics['cpu_percent']}% | Memory {metrics['memory_percent']}% | Disk {metrics['disk_percent']}% | Backend {metrics['backend_status']}")

if __name__ == '__main__':
    check_system_health()
EOF

    chmod +x "${APP_DIR}/monitor.py"
    chown "${SYSTEM_USER}:${SYSTEM_USER}" "${APP_DIR}/monitor.py"
    
    # Add monitoring cron job
    echo "*/5 * * * * ${SYSTEM_USER} cd ${APP_DIR} && ./venv/bin/python monitor.py" >> /etc/crontab
    
    print_success "Logging and monitoring configured"
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

main() {
    print_status "Starting AssisText Backend Setup..."
    print_status "Configuration: DB=${DB_NAME}, User=${DB_USER}, Port=${BACKEND_PORT}, Dir=${APP_DIR}"
    
    # Check if running as root
    check_root
    
    # Run setup steps
    install_system_dependencies
    setup_postgresql
    setup_redis
    setup_python_environment
    create_application_files
    initialize_database_schema
    create_systemd_services
    setup_logging
    test_installation
    
    print_success "==================================================================="
    print_success "AssisText Backend Setup Complete!"
    print_success "==================================================================="
    print_status "Service Details:"
    print_status "- Backend URL: http://localhost:${BACKEND_PORT}"
    print_status "- Nginx Proxy: http://localhost"
    print_status "- Database: ${DB_NAME} (user: ${DB_USER})"
    print_status "- Redis: localhost:6379 (password protected)"
    print_status "- Application Directory: ${APP_DIR}"
    print_status "- Log Directory: ${LOG_DIR}"
    print_status ""
    print_status "Service Management:"
    print_status "- Start: systemctl start assistext-backend"
    print_status "- Stop: systemctl stop assistext-backend"
    print_status "- Status: systemctl status assistext-backend"
    print_status "- Logs: journalctl -u assistext-backend -f"
    print_status ""
    print_status "API Endpoints:"
    print_status "- Health: GET /health"
    print_status "- Register: POST /api/auth/register"
    print_status "- Search Numbers: POST /api/signup/search-numbers"
    print_status "- Complete Signup: POST /api/signup/complete-signup"
    print_status ""
    print_warning "Next Steps:"
    print_warning "1. Update SignalWire credentials in ${APP_DIR}/.env"
    print_warning "2. Configure email settings if needed"
    print_warning "3. Test API endpoints with your frontend"
    print_warning "4. Set up SSL certificate for production"
    print_success "==================================================================="
}

# Run the main function
main

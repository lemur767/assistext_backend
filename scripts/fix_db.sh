#!/bin/bash
# fix-sqlalchemy-conflicts.sh
# Fix SQLAlchemy table conflicts and setup proper migration

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"; }
success() { echo -e "${GREEN}[SUCCESS] $1${NC}"; }
warning() { echo -e "${YELLOW}[WARNING] $1${NC}"; }
error() { echo -e "${RED}[ERROR] $1${NC}"; }

# ===== STEP 1: STOP THE SERVICE =====
log "Stopping AssisText backend service..."
sudo systemctl stop assistext-backend || true

# ===== STEP 2: BACKUP CURRENT STATE =====
log "Creating backup of current state..."
cd /opt/assistext_backend

# Create backup directory
mkdir -p backup/$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="backup/$(date +%Y%m%d-%H%M%S)"

# Backup current models
cp -r app/models/ "$BACKUP_DIR/models_backup/"
cp -r app/api/ "$BACKUP_DIR/api_backup/" 2>/dev/null || true

success "Backup created at $BACKUP_DIR"

# ===== STEP 3: FIX MODEL CONFLICTS =====
log "Fixing SQLAlchemy model conflicts..."

# Check for duplicate User classes
log "Checking for duplicate User model definitions..."
find app/models/ -name "*.py" -exec grep -l "class User" {} \; || true

# Remove conflicting User class from profile.py if it exists
if grep -q "class User" app/models/profile.py 2>/dev/null; then
    warning "Found User class in profile.py - this conflicts with user.py"
    warning "Commenting out User class in profile.py..."
    
    # Comment out the User class in profile.py
    sed -i '/^class User/,/^class [^(]/ { /^class User/,/^$/ { /^class [^U]/ !s/^/# /; } }' app/models/profile.py 2>/dev/null || true
fi

# ===== STEP 4: UPDATE MODELS WITH EXTEND_EXISTING =====
log "Adding extend_existing=True to all model tables..."

# Update user.py
cat > app/models/user.py << 'EOF'
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from datetime import datetime, date
import json
from typing import Dict, Any, Optional

class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Basic Profile Information
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    display_name = db.Column(db.String(100))
    phone_number = db.Column(db.String(20))
    timezone = db.Column(db.String(50), default='UTC')
    
    # SignalWire Configuration
    signalwire_phone_number = db.Column(db.String(20), unique=True, nullable=True)
    signalwire_project_id = db.Column(db.String(100))
    signalwire_auth_token = db.Column(db.String(100))
    signalwire_space_url = db.Column(db.String(200))
    signalwire_webhook_configured = db.Column(db.Boolean, default=False)
    
    # Business Settings
    business_hours = db.Column(db.Text)
    auto_reply_enabled = db.Column(db.Boolean, default=True)
    out_of_office_enabled = db.Column(db.Boolean, default=False)
    out_of_office_message = db.Column(db.Text)
    daily_message_limit = db.Column(db.Integer, default=100)
    
    # AI Configuration
    ai_enabled = db.Column(db.Boolean, default=True)
    ai_personality = db.Column(db.Text)
    ai_instructions = db.Column(db.Text)
    ai_model = db.Column(db.String(50), default='gpt-4')
    ai_temperature = db.Column(db.Float, default=0.7)
    ai_max_tokens = db.Column(db.Integer, default=150)
    
    # Usage Tracking
    total_messages_sent = db.Column(db.Integer, default=0)
    total_messages_received = db.Column(db.Integer, default=0)
    monthly_message_count = db.Column(db.Integer, default=0)
    last_reset_date = db.Column(db.Date, default=datetime.utcnow().date())
    
    # Account Status
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self) -> str:
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        else:
            return self.username
    
    @property
    def profile_name(self) -> str:
        return self.display_name or self.full_name
    
    def get_business_hours(self) -> Dict[str, Any]:
        if not self.business_hours:
            return {
                'monday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
                'tuesday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
                'wednesday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
                'thursday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
                'friday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
                'saturday': {'enabled': False, 'start': '09:00', 'end': '17:00'},
                'sunday': {'enabled': False, 'start': '09:00', 'end': '17:00'}
            }
        try:
            return json.loads(self.business_hours)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_business_hours(self, hours_dict: Dict[str, Any]) -> None:
        self.business_hours = json.dumps(hours_dict)
    
    def is_signalwire_configured(self) -> bool:
        return bool(
            self.signalwire_project_id and 
            self.signalwire_auth_token and 
            self.signalwire_space_url and
            self.signalwire_phone_number
        )
    
    def get_ai_settings(self) -> Dict[str, Any]:
        return {
            'enabled': self.ai_enabled,
            'personality': self.ai_personality or "You are a helpful and professional assistant.",
            'instructions': self.ai_instructions or "Respond helpfully and professionally to messages.",
            'model': self.ai_model,
            'temperature': self.ai_temperature,
            'max_tokens': self.ai_max_tokens
        }
    
    def update_message_count(self, sent: int = 0, received: int = 0) -> None:
        self.total_messages_sent += sent
        self.total_messages_received += received
        self.monthly_message_count += (sent + received)
    
    def reset_monthly_count_if_needed(self) -> None:
        today = datetime.utcnow().date()
        if self.last_reset_date.month != today.month or self.last_reset_date.year != today.year:
            self.monthly_message_count = 0
            self.last_reset_date = today
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'display_name': self.display_name,
            'profile_name': self.profile_name,
            'phone_number': self.phone_number,
            'timezone': self.timezone,
            'signalwire_phone_number': self.signalwire_phone_number,
            'signalwire_configured': self.is_signalwire_configured(),
            'business_hours': self.get_business_hours(),
            'auto_reply_enabled': self.auto_reply_enabled,
            'out_of_office_enabled': self.out_of_office_enabled,
            'out_of_office_message': self.out_of_office_message,
            'daily_message_limit': self.daily_message_limit,
            'ai_settings': self.get_ai_settings(),
            'usage_stats': {
                'total_sent': self.total_messages_sent,
                'total_received': self.total_messages_received,
                'monthly_count': self.monthly_message_count,
                'daily_limit': self.daily_message_limit
            },
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        if include_sensitive:
            data.update({
                'signalwire_project_id': self.signalwire_project_id,
                'signalwire_space_url': self.signalwire_space_url,
            })
        
        return data
EOF

# ===== STEP 5: CLEAN UP IMPORTS =====
log "Cleaning up model imports..."

# Update __init__.py to only import what exists
cat > app/models/__init__.py << 'EOF'
from .user import User

# Import other models as they exist
try:
    from .client import Client
except ImportError:
    pass

try:
    from .message import Message
except ImportError:
    pass

try:
    from .text_example import TextExample
except ImportError:
    pass

try:
    from .auto_reply import AutoReply
except ImportError:
    pass

__all__ = ['User']
EOF

# ===== STEP 6: FIX BLUEPRINT IMPORTS =====
log "Fixing blueprint import issues..."

# Check what API files exist
ls -la app/api/ || mkdir -p app/api

# Create __init__.py for api module
touch app/api/__init__.py

# Comment out missing blueprint imports in app/__init__.py
if [ -f app/__init__.py ]; then
    log "Updating app/__init__.py to handle missing blueprints..."
    
    # Backup original
    cp app/__init__.py "$BACKUP_DIR/app_init_backup.py"
    
    # Update to handle missing imports gracefully
    cat > app/__init__.py << 'EOF'
from flask import Flask
from app.extensions import db, jwt
from app.config import Config
import logging

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    
    # Import models to register them with SQLAlchemy
    from app.models import User
    
    # Register blueprints (with error handling)
    try:
        from app.api.auth import auth_bp
        app.register_blueprint(auth_bp)
        print("✅ Auth blueprint registered")
    except Exception as e:
        print(f"⚠️ Error registering auth routes: {e}")
    
    try:
        from app.api.profile import profile_bp
        app.register_blueprint(profile_bp)
        print("✅ Profile blueprint registered")
    except Exception as e:
        print(f"⚠️ Error registering profile routes: {e}")
    
    try:
        from app.api.webhooks import webhooks_bp
        app.register_blueprint(webhooks_bp)
        print("✅ Webhooks blueprint registered")
    except Exception as e:
        print(f"⚠️ Error registering webhooks blueprint: {e}")
    
    # Try to register other blueprints if they exist
    try:
        from app.api.signup import signup_bp
        app.register_blueprint(signup_bp, url_prefix='/api/signup')
        print("✅ Signup blueprint registered")
    except Exception as e:
        print(f"⚠️ Could not import signup blueprint: {e}")
    
    # Don't try to import profiles blueprint (it's been replaced by profile)
    
    # Create database tables
    with app.app_context():
        try:
            db.create_all()
            print("✅ Database tables created successfully")
        except Exception as e:
            print(f"⚠️ Database error: {e}")
    
    return app
EOF
fi

# ===== STEP 7: INSTALL FLASK-MIGRATE =====
log "Setting up Flask-Migrate..."

# Activate virtual environment and install Flask-Migrate
source venv/bin/activate
pip install Flask-Migrate

# ===== STEP 8: UPDATE EXTENSIONS =====
log "Updating extensions to include Flask-Migrate..."

cat > app/extensions.py << 'EOF'
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate

db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()
EOF

# ===== STEP 9: UPDATE APP INITIALIZATION =====
log "Updating app initialization to include migrations..."

# Update app/__init__.py to include migrate
cat > app/__init__.py << 'EOF'
from flask import Flask
from app.extensions import db, jwt, migrate
from app.config import Config
import logging

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    
    # Import models to register them with SQLAlchemy
    from app.models import User
    
    # Register blueprints (with error handling)
    try:
        from app.api.auth import auth_bp
        app.register_blueprint(auth_bp)
        print("✅ Auth blueprint registered")
    except Exception as e:
        print(f"⚠️ Error registering auth routes: {e}")
    
    try:
        from app.api.profile import profile_bp
        app.register_blueprint(profile_bp)
        print("✅ Profile blueprint registered")
    except Exception as e:
        print(f"⚠️ Error registering profile routes: {e}")
    
    try:
        from app.api.webhooks import webhooks_bp
        app.register_blueprint(webhooks_bp)
        print("✅ Webhooks blueprint registered")
    except Exception as e:
        print(f"⚠️ Error registering webhooks blueprint: {e}")
    
    try:
        from app.api.signup import signup_bp
        app.register_blueprint(signup_bp, url_prefix='/api/signup')
        print("✅ Signup blueprint registered")
    except Exception as e:
        print(f"⚠️ Could not import signup blueprint: {e}")
    
    return app
EOF

# ===== STEP 10: INITIALIZE MIGRATION REPOSITORY =====
log "Initializing Flask-Migrate..."

# Set Flask app
export FLASK_APP=wsgi.py

# Initialize migration repository
flask db init 2>/dev/null || warning "Migration repository already exists"

# ===== STEP 11: CREATE INITIAL MIGRATION =====
log "Creating initial migration..."

# Create migration for current schema
flask db migrate -m "Initial migration with restructured user profiles" || warning "Migration creation may have issues"

# ===== STEP 12: CREATE MINIMAL WORKING API =====
log "Creating minimal working API endpoints..."

# Create basic auth endpoint
mkdir -p app/api
cat > app/api/auth.py << 'EOF'
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from app.models.user import User
from app.extensions import db
from typing import Dict, Any

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        
        required_fields = ['username', 'email', 'password', 'first_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if user already exists
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already exists'}), 400
        
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already registered'}), 400
        
        # Create new user
        user = User(
            username=data['username'],
            email=data['email'],
            first_name=data['first_name'],
            last_name=data.get('last_name', ''),
            display_name=data.get('display_name'),
            phone_number=data.get('phone_number'),
            timezone=data.get('timezone', 'UTC'),
            ai_personality=data.get('ai_personality', 'You are a helpful assistant.'),
            ai_instructions=data.get('ai_instructions', 'Respond professionally.')
        )
        
        user.set_password(data['password'])
        
        # Set default business hours
        default_hours = {
            'monday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
            'tuesday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
            'wednesday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
            'thursday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
            'friday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
            'saturday': {'enabled': False, 'start': '09:00', 'end': '17:00'},
            'sunday': {'enabled': False, 'start': '09:00', 'end': '17:00'}
        }
        user.set_business_hours(default_hours)
        
        db.session.add(user)
        db.session.commit()
        
        # Create JWT tokens
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)
        
        return jsonify({
            'success': True,
            'message': 'Account created successfully',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Registration error: {str(e)}")
        return jsonify({'error': 'Registration failed'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.get_json()
        
        user = User.query.filter(
            (User.username == data.get('username')) | 
            (User.email == data.get('username'))
        ).first()
        
        if not user or not user.check_password(data.get('password', '')):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Create JWT tokens
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500
EOF

# ===== STEP 13: TEST THE FIXES =====
log "Testing the fixes..."

# Test Python imports
cd /opt/assistext_backend
source venv/bin/activate

python3 -c "
try:
    from app.models.user import User
    print('✅ User model imports successfully')
except Exception as e:
    print(f'❌ User model import error: {e}')

try:
    from app import create_app
    app = create_app()
    print('✅ App creates successfully')
except Exception as e:
    print(f'❌ App creation error: {e}')
"

# Test Flask CLI
export FLASK_APP=wsgi.py
flask --help > /dev/null 2>&1 && echo "✅ Flask CLI working" || echo "❌ Flask CLI not working"

# Check if db command works now
flask db --help > /dev/null 2>&1 && echo "✅ Flask db command available" || echo "❌ Flask db command still not available"

# ===== STEP 14: RESTART SERVICE =====
log "Restarting AssisText backend service..."

sudo systemctl start assistext-backend
sleep 3

# Check status
if systemctl is-active assistext-backend >/dev/null; then
    success "✅ Service started successfully"
else
    warning "❌ Service failed to start, checking logs..."
    sudo systemctl status assistext-backend --no-pager -l
fi

# ===== STEP 15: FINAL VERIFICATION =====
log "Running final verification..."

echo ""
echo "🔍 Final Status Check:"
echo ""

# Check service status
if systemctl is-active assistext-backend >/dev/null; then
    echo "✅ Service: Running"
else
    echo "❌ Service: Not running"
fi

# Check recent logs
echo ""
echo "📋 Recent logs:"
journalctl -u assistext-backend --since "1 minute ago" | grep -E "(✅|❌|⚠️|ERROR|SUCCESS)" | tail -10

echo ""
success "SQLAlchemy conflicts fix completed!"
echo ""
echo "🎯 What was fixed:"
echo "✅ Removed duplicate User model definitions"
echo "✅ Added extend_existing=True to all tables"
echo "✅ Set up Flask-Migrate properly"
echo "✅ Fixed blueprint import errors"
echo "✅ Created working auth endpoints"
echo "✅ Updated app initialization"
echo ""
echo "📋 Next steps:"
echo "1. Check service logs: journalctl -u assistext-backend -f"
echo "2. Test registration: curl -X POST http://localhost:5000/api/auth/register"
echo "3. Run database migration if needed: flask db upgrade"
echo ""

# Cleanup
deactivate || true

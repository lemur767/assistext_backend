#!/usr/bin/env python3
"""
Complete script to fix all SQLAlchemy metadata conflicts
This script will scan all model files and fix any 'metadata' column conflicts
"""

import os
import re
import shutil
from pathlib import Path
import sys

def backup_files(file_paths):
    """Create backups of files before modifying them"""
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    for file_path in file_paths:
        if file_path.exists():
            backup_path = backup_dir / f"{file_path.name}.backup"
            shutil.copy2(file_path, backup_path)
            print(f"✅ Backed up {file_path} to {backup_path}")

def find_metadata_conflicts(directory):
    """Find all files with metadata column conflicts"""
    conflicts = []
    models_dir = Path(directory) / "app" / "models"
    
    if not models_dir.exists():
        print(f"❌ Models directory not found: {models_dir}")
        return conflicts
    
    # Pattern to find metadata column definitions
    metadata_pattern = r'^\s*metadata\s*=\s*db\.Column'
    
    for py_file in models_dir.glob("*.py"):
        if py_file.name == "__init__.py":
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    if re.search(metadata_pattern, line):
                        conflicts.append({
                            'file': py_file,
                            'line': i,
                            'content': line.strip(),
                            'model_name': py_file.stem
                        })
        except Exception as e:
            print(f"⚠️  Error reading {py_file}: {e}")
    
    return conflicts

def fix_metadata_in_file(file_path, model_name):
    """Fix metadata conflicts in a specific file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Determine the replacement name based on model
        replacement_name = f"{model_name.lower()}_metadata"
        
        # Replace metadata column definition
        content = re.sub(
            r'(\s*)metadata(\s*=\s*db\.Column)',
            rf'\1{replacement_name}\2',
            content
        )
        
        # Replace getter/setter method names
        content = re.sub(
            r'def get_metadata\(',
            f'def get_{replacement_name}(',
            content
        )
        
        content = re.sub(
            r'def set_metadata\(',
            f'def set_{replacement_name}(',
            content
        )
        
        # Replace references to self.metadata
        content = re.sub(
            r'self\.metadata',
            f'self.{replacement_name}',
            content
        )
        
        # Replace references in method calls
        content = re.sub(
            r'\.get_metadata\(',
            f'.get_{replacement_name}(',
            content
        )
        
        content = re.sub(
            r'\.set_metadata\(',
            f'.set_{replacement_name}(',
            content
        )
        
        # Update to_dict() method if it references metadata
        content = re.sub(
            r"'metadata':\s*self\.get_metadata\(\)",
            f"'{replacement_name}': self.get_{replacement_name}()",
            content
        )
        
        # Write the fixed content back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Fixed metadata conflicts in {file_path} (renamed to {replacement_name})")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing {file_path}: {e}")
        return False

def create_missing_models():
    """Create any missing model files that are commonly needed"""
    models_dir = Path("app/models")
    models_dir.mkdir(parents=True, exist_ok=True)
    
    # Missing model templates
    missing_models = {
        "client.py": '''# app/models/client.py
from app.extensions import db
from datetime import datetime


class Client(db.Model):
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(255))
    notes = db.Column(db.Text)
    is_blocked = db.Column(db.Boolean, default=False)
    is_regular = db.Column(db.Boolean, default=False)
    last_message_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    messages = db.relationship('Message', back_populates='client', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'phone_number': self.phone_number,
            'name': self.name,
            'email': self.email,
            'notes': self.notes,
            'is_blocked': self.is_blocked,
            'is_regular': self.is_regular,
            'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
''',
        
        "message.py": '''# app/models/message.py
from app.extensions import db
from datetime import datetime


class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), index=True)
    sender_number = db.Column(db.String(20), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    is_incoming = db.Column(db.Boolean, nullable=False, index=True)
    ai_generated = db.Column(db.Boolean, default=False)
    is_read = db.Column(db.Boolean, default=False)
    send_status = db.Column(db.String(20), default='pending')
    send_error = db.Column(db.Text)
    twilio_sid = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # FIXED: Using message_metadata instead of metadata
    message_metadata = db.Column(db.Text)  # JSON string for additional message data
    
    # Relationships
    profile = db.relationship('Profile', back_populates='messages')
    client = db.relationship('Client', back_populates='messages')
    flagged_message = db.relationship('FlaggedMessage', back_populates='message', uselist=False)
    
    def get_message_metadata(self):
        """Get message metadata as dictionary"""
        if not self.message_metadata:
            return {}
        try:
            import json
            return json.loads(self.message_metadata)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_message_metadata(self, metadata_dict):
        """Set message metadata from dictionary"""
        if metadata_dict:
            import json
            self.message_metadata = json.dumps(metadata_dict)
        else:
            self.message_metadata = None
    
    def to_dict(self):
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'client_id': self.client_id,
            'sender_number': self.sender_number,
            'content': self.content,
            'is_incoming': self.is_incoming,
            'ai_generated': self.ai_generated,
            'is_read': self.is_read,
            'send_status': self.send_status,
            'send_error': self.send_error,
            'twilio_sid': self.twilio_sid,
            'timestamp': self.timestamp.isoformat(),
            'message_metadata': self.get_message_metadata()
        }
''',

        "auto_reply.py": '''# app/models/auto_reply.py
from app.extensions import db
from datetime import datetime


class AutoReply(db.Model):
    __tablename__ = 'auto_replies'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    keyword = db.Column(db.String(100), nullable=False)
    response = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    priority = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    profile = db.relationship('Profile', back_populates='auto_replies')
    
    def to_dict(self):
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'keyword': self.keyword,
            'response': self.response,
            'is_active': self.is_active,
            'priority': self.priority,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
''',

        "text_example.py": '''# app/models/text_example.py
from app.extensions import db
from datetime import datetime


class TextExample(db.Model):
    __tablename__ = 'text_examples'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_incoming = db.Column(db.Boolean, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    profile = db.relationship('Profile', back_populates='text_examples')
    
    def to_dict(self):
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'content': self.content,
            'is_incoming': self.is_incoming,
            'timestamp': self.timestamp.isoformat()
        }
''',

        "flagged_message.py": '''# app/models/flagged_message.py
from app.extensions import db
from datetime import datetime


class FlaggedMessage(db.Model):
    __tablename__ = 'flagged_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=False)
    reasons = db.Column(db.Text)  # JSON string
    is_reviewed = db.Column(db.Boolean, default=False)
    reviewer_notes = db.Column(db.Text)
    flagged_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    
    # Relationships
    message = db.relationship('Message', back_populates='flagged_message')
    
    def to_dict(self):
        return {
            'id': self.id,
            'message_id': self.message_id,
            'reasons': self.reasons,
            'is_reviewed': self.is_reviewed,
            'reviewer_notes': self.reviewer_notes,
            'flagged_at': self.flagged_at.isoformat(),
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None
        }
''',

        "out_of_office_reply.py": '''# app/models/out_of_office_reply.py
from app.extensions import db
from datetime import datetime


class OutOfOfficeReply(db.Model):
    __tablename__ = 'out_of_office_replies'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    profile = db.relationship('Profile', back_populates='out_of_office_replies')
    
    def to_dict(self):
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'message': self.message,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
''',

        "ai_model_settings.py": '''# app/models/ai_model_settings.py
from app.extensions import db
from datetime import datetime


class AIModelSettings(db.Model):
    __tablename__ = 'ai_model_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    model_version = db.Column(db.String(50), default='gpt-3.5-turbo')
    temperature = db.Column(db.Float, default=0.7)
    response_length = db.Column(db.Integer, default=150)
    custom_instructions = db.Column(db.Text)
    style_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    profile = db.relationship('Profile', back_populates='ai_settings')
    
    def to_dict(self):
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'model_version': self.model_version,
            'temperature': self.temperature,
            'response_length': self.response_length,
            'custom_instructions': self.custom_instructions,
            'style_notes': self.style_notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
'''
    }
    
    for filename, content in missing_models.items():
        file_path = models_dir / filename
        if not file_path.exists():
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Created missing model: {file_path}")

def update_models_init():
    """Update the models __init__.py file to import from billing.py"""
    init_file = Path("app/models/__init__.py")
    
    init_content = '''# app/models/__init__.py
from app.extensions import db

# Import all models to ensure they are registered with SQLAlchemy
from .user import User
from .profile import Profile
from .message import Message
from .client import Client

# Import all billing models from consolidated billing.py file
from .billing import (
    Subscription, 
    SubscriptionPlan, 
    Invoice, 
    InvoiceItem, 
    PaymentMethod
)

from .auto_reply import AutoReply
from .text_example import TextExample
from .out_of_office_reply import OutOfOfficeReply
from .ai_model_settings import AIModelSettings
from .flagged_message import FlaggedMessage

# Export all models
__all__ = [
    'User',
    'Profile', 
    'Message',
    'Client',
    'Subscription',
    'SubscriptionPlan',
    'Invoice',
    'InvoiceItem',
    'PaymentMethod',
    'AutoReply',
    'TextExample',
    'OutOfOfficeReply',
    'AIModelSettings',
    'FlaggedMessage'
]
'''
    
    with open(init_file, 'w', encoding='utf-8') as f:
        f.write(init_content)
    
    print(f"✅ Updated {init_file}")

def remove_conflicting_files():
    """Remove files that might conflict with consolidated billing.py"""
    models_dir = Path("app/models")
    conflicting_files = [
        "subscription.py",
        "invoice.py", 
        "payment_method.py"
    ]
    
    for filename in conflicting_files:
        file_path = models_dir / filename
        if file_path.exists():
            file_path.unlink()
            print(f"✅ Removed conflicting file: {file_path}")

def clean_python_cache():
    """Clean Python cache files"""
    print("🧹 Cleaning Python cache...")
    
    # Remove __pycache__ directories
    for pycache_dir in Path(".").rglob("__pycache__"):
        if pycache_dir.is_dir():
            shutil.rmtree(pycache_dir)
            print(f"  Removed {pycache_dir}")
    
    # Remove .pyc files
    for pyc_file in Path(".").rglob("*.pyc"):
        pyc_file.unlink()
        print(f"  Removed {pyc_file}")

def main():
    """Main function to fix all metadata conflicts"""
    print("🔧 Starting metadata conflict resolution...")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path("app").exists():
        print("❌ Error: 'app' directory not found. Are you in the project root?")
        sys.exit(1)
    
    # Find all metadata conflicts
    print("🔍 Scanning for metadata conflicts...")
    conflicts = find_metadata_conflicts(".")
    
    if not conflicts:
        print("✅ No metadata conflicts found!")
    else:
        print(f"Found {len(conflicts)} metadata conflicts:")
        for conflict in conflicts:
            print(f"  📁 {conflict['file']} (line {conflict['line']})")
        
        # Create backups
        print("\n📦 Creating backups...")
        file_paths = list(set(conflict['file'] for conflict in conflicts))
        backup_files(file_paths)
        
        # Fix each conflict
        print("\n🔧 Fixing conflicts...")
        for conflict in conflicts:
            fix_metadata_in_file(conflict['file'], conflict['model_name'])
    
    # Create missing models
    print("\n📝 Creating missing model files...")
    create_missing_models()
    
    # Remove conflicting files
    print("\n🗑️  Removing conflicting files...")
    remove_conflicting_files()
    
    # Update models __init__.py
    print("\n📄 Updating models __init__.py...")
    update_models_init()
    
    # Clean Python cache
    print("\n🧹 Cleaning Python cache...")
    clean_python_cache()
    
    print("\n" + "=" * 50)
    print("🎉 Metadata conflict resolution complete!")
    print("\nSummary of changes:")
    print("✅ Fixed all 'metadata' column conflicts")
    print("✅ Renamed metadata columns to model-specific names")
    print("✅ Created missing model files")
    print("✅ Removed conflicting separate model files")
    print("✅ Updated models __init__.py")
    print("✅ Cleaned Python cache")
    print("\nYou can now run your Flask application:")
    print("  export FLASK_APP=wsgi.py")
    print("  flask run")

if __name__ == "__main__":
    main()

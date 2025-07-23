from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    jwt_required, get_jwt_identity, create_access_token, 
    create_refresh_token, get_jwt
)
from app.models.user import User
from app.extensions import db
from datetime import datetime, timedelta, date
import re
import json

from decimal import Decimal
import base64
import logging

from app.services.signalwire_service import get_signalwire_service  # Make sure this import path is correct
from flask_cors import cross_origin



class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, bytes):
            try:
                return obj.decode('utf-8')
            except UnicodeDecodeError:
                return base64.b64encode(obj).decode('ascii')
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        return super().default(obj)

def safe_jsonify(data, status_code=200):
    try:
        json_string = json.dumps(data, cls=CustomJSONEncoder)
        parsed_data = json.loads(json_string)
        response = jsonify(parsed_data)
        response.status_code = status_code
        return response
    except Exception as e:
        current_app.logger.error(f"JSON serialization failed: {e}")
        return jsonify({'error': 'Response serialization failed'}), 500

auth_bp = Blueprint('auth', __name__)




auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST', 'OPTIONS'])
@cross_origin()
def register_user():
    """
    Enhanced registration that automatically sets up SignalWire tenant
    Creates: User + 14-day trial + SignalWire subproject + phone number
    """
    try:
        if request.method == 'OPTIONS':
            return '', 204
        
        data = request.get_json() or {}
        
        # Validate required fields
        required_fields = ['username', 'email', 'password', 'first_name', 'last_name']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return jsonify({
                'success': False,
                'error': f"Missing required fields: {', '.join(missing_fields)}"
            }), 400
        
        # Check if user already exists
        existing_user = User.query.filter(
            (User.email == data['email']) | (User.username == data['username'])
        ).first()
        
        if existing_user:
            return jsonify({
                'success': False,
                'error': 'User with this email or username already exists'
            }), 400
        
        logging.info(f"🚀 Starting registration for: {data['email']}")
        
        # Step 1: Create user with trial settings
        trial_end_date = datetime.utcnow() + timedelta(days=14)
        
        new_user = User(
            username=data['username'],
            email=data['email'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            personal_phone=data.get('personal_phone'),
            
            # Trial settings
            is_trial=True,
            trial_status='active',
            trial_start_date=datetime.utcnow(),
            trial_end_date=trial_end_date,
            trial_days_remaining=14,
            
            # SignalWire setup flags
            signalwire_setup_pending=True,
            signalwire_setup_completed=False
        )
        
        # Set password hash
        new_user.set_password(data['password'])
        
        # Save user first to get ID
        db.session.add(new_user)
        db.session.flush()  # Get the user ID without committing
        
        user_id = new_user.id
        logging.info(f"✅ User created with ID: {user_id}")
        
        # Step 2: Automatic SignalWire tenant setup
        signalwire = get_signalwire_service()
        
        # Determine phone search criteria based on user preference or default
        phone_search_criteria = {
            'country': data.get('preferred_country', 'US'),
            'area_code': data.get('preferred_area_code'),
            'region': data.get('preferred_region'),
            'limit': 5  # Search 5 numbers and pick the first available
        }
        
        # Remove None values
        phone_search_criteria = {k: v for k, v in phone_search_criteria.items() if v is not None}
        
        logging.info(f"🔍 Setting up SignalWire tenant for user {user_id}")
        
        tenant_setup_result = signalwire.setup_new_tenant(
            user_id=user_id,
            friendly_name=f"{data['first_name']}_{data['last_name']}",
            phone_search_criteria=phone_search_criteria
        )
        
        if tenant_setup_result['success']:
            # Step 3: Update user with SignalWire details
            tenant_data = tenant_setup_result['tenant_setup']
            
            new_user.signalwire_subproject_id = tenant_data['subproject']['subproject_sid']
            new_user.signalwire_auth_token = tenant_data['subproject']['auth_token']
            new_user.signalwire_phone_number = tenant_data['phone_number']['phone_number']
            new_user.signalwire_phone_sid = tenant_data['phone_number']['phone_number_sid']
            new_user.signalwire_setup_completed = True
            new_user.signalwire_setup_pending = False
            new_user.signalwire_number_active = True  # Active during trial
            
            # Commit all changes
            db.session.commit()
            
            logging.info(f"✅ Complete registration successful for {data['email']}")
            logging.info(f"📞 Assigned phone number: {new_user.signalwire_phone_number}")
            
            # Step 4: Schedule trial expiry task
            from app.tasks.trial_tasks import schedule_trial_expiry
            schedule_trial_expiry.delay(user_id, trial_end_date.isoformat())
            
            # Step 5: Send welcome email with trial info
            from app.tasks.email_tasks import send_welcome_email
            send_welcome_email.delay(
                user_id=user_id,
                email=new_user.email,
                first_name=new_user.first_name,
                trial_end_date=trial_end_date.isoformat(),
                phone_number=new_user.signalwire_phone_number
            )
            
            return jsonify({
                'success': True,
                'message': 'Registration successful! Your 14-day trial has started.',
                'user': {
                    'id': new_user.id,
                    'username': new_user.username,
                    'email': new_user.email,
                    'first_name': new_user.first_name,
                    'last_name': new_user.last_name,
                    'trial_status': 'active',
                    'trial_end_date': trial_end_date.isoformat(),
                    'trial_days_remaining': 14
                },
                'signalwire': {
                    'phone_number': new_user.signalwire_phone_number,
                    'setup_completed': True,
                    'number_active': True,
                    'subproject_id': new_user.signalwire_subproject_id
                },
                'trial': {
                    'active': True,
                    'days_remaining': 14,
                    'end_date': trial_end_date.isoformat(),
                    'features_included': [
                        'Automated SMS responses',
                        'AI-powered message handling',
                        'Basic analytics',
                        'Webhook integration'
                    ]
                }
            })
            
        else:
            # SignalWire setup failed - rollback user creation
            db.session.rollback()
            
            logging.error(f"❌ SignalWire setup failed for {data['email']}: {tenant_setup_result['error']}")
            
            return jsonify({
                'success': False,
                'error': 'Registration failed during phone number setup. Please try again.',
                'details': tenant_setup_result['error']
            }), 500
            
    except Exception as e:
        db.session.rollback()
        logging.error(f"❌ Registration error: {str(e)}")
        
        return jsonify({
            'success': False,
            'error': 'Registration failed due to an internal error. Please try again.'
        }), 500


@auth_bp.route('/trial-status/<int:user_id>', methods=['GET'])
def get_trial_status(user_id):
    """Get current trial status for a user"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        if not user.is_trial:
            return jsonify({
                'success': True,
                'trial_active': False,
                'message': 'User is not on trial'
            })
        
        # Calculate remaining days
        if user.trial_end_date:
            remaining_time = user.trial_end_date - datetime.utcnow()
            days_remaining = max(0, remaining_time.days)
            
            return jsonify({
                'success': True,
                'trial_active': user.trial_status == 'active',
                'trial_status': user.trial_status,
                'days_remaining': days_remaining,
                'trial_end_date': user.trial_end_date.isoformat(),
                'signalwire_number_active': user.signalwire_number_active,
                'phone_number': user.signalwire_phone_number
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Trial end date not set'
            })
            
    except Exception as e:
        logging.error(f"Error getting trial status: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get trial status'
        }), 500
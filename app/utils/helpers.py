# =============================================================================
# app/utils/helpers.py
"""
GENERAL HELPER FUNCTIONS - CORRECTED VERSION
Email, notifications, and utility functions with proper trial management
"""
import os
import uuid
import json
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from datetime import datetime
from typing import Dict, Any, Optional
from flask import current_app, request


def generate_invoice_number() -> str:
    """Generate unique invoice number"""
    timestamp = datetime.utcnow().strftime('%Y%m%d')
    random_suffix = str(uuid.uuid4().hex)[:8].upper()
    return f"INV-{timestamp}-{random_suffix}"


def send_email(to_email: str, subject: str, html_content: str, 
               text_content: str = None) -> Dict:
    """Send email using SMTP with proper configuration"""
    try:
        # Email configuration from actual environment variables
        smtp_server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('MAIL_PORT', 587))
        smtp_username = os.getenv('MAIL_USERNAME')
        smtp_password = os.getenv('MAIL_PASSWORD')
        from_email = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@assitext.ca')
        
        if not all([smtp_username, smtp_password]):
            return {'success': False, 'error': 'Email configuration missing'}
        
        # Create message
        message = MimeMultipart('alternative')
        message['Subject'] = subject
        message['From'] = from_email
        message['To'] = to_email
        
        # Add text part
        if text_content:
            text_part = MimeText(text_content, 'plain')
            message.attach(text_part)
        
        # Add HTML part
        html_part = MimeText(html_content, 'html')
        message.attach(html_part)
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(message)
        
        current_app.logger.info(f"Email sent successfully to: {to_email}")
        return {'success': True}
        
    except Exception as e:
        current_app.logger.error(f"Failed to send email: {e}")
        return {'success': False, 'error': str(e)}


def send_welcome_email(user_data: Dict) -> Dict:
    """Send welcome email to new user with trial information"""
    subject = "Welcome to AssisText - Your SMS AI Assistant!"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Welcome to AssisText</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #2c3e50;">Welcome to AssisText!</h1>
            
            <p>Hi {user_data.get('first_name', user_data.get('username'))}!</p>
            
            <p>Thank you for signing up for AssisText - your AI-powered SMS assistant platform.</p>
            
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <h3>Account Details:</h3>
                <p><strong>Username:</strong> {user_data.get('username')}</p>
                <p><strong>Email:</strong> {user_data.get('email')}</p>
                <p><strong>Account Created:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>
                <p><strong>Stripe Customer ID:</strong> {user_data.get('stripe_customer_id', 'Setup pending')}</p>
            </div>
            
            <div style="background-color: #e8f4fd; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <h3>Next Steps to Start Your 14-Day Trial:</h3>
                <ol>
                    <li><strong>Add a Payment Method</strong> - Required for trial activation</li>
                    <li><strong>Choose Your Phone Number</strong> - Select your preferred area code</li>
                    <li><strong>Configure Your AI Assistant</strong> - Set personality and response style</li>
                    <li><strong>Start Receiving SMS</strong> - Your AI will handle messages automatically</li>
                </ol>
                
                <div style="text-align: center; margin: 20px 0;">
                    <a href="https://assitext.ca/dashboard/trial-setup" 
                       style="background-color: #007bff; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                        Start Your Trial →
                    </a>
                </div>
            </div>
            
            <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h4>🎯 What You Get During Your Trial:</h4>
                <ul>
                    <li>Your own dedicated SignalWire phone number</li>
                    <li>AI-powered SMS responses (up to 100/day)</li>
                    <li>Client management and conversation history</li>
                    <li>Business hours and auto-reply configuration</li>
                    <li>Real-time usage tracking and analytics</li>
                </ul>
            </div>
            
            <p>If you have any questions, please don't hesitate to contact our support team at support@assitext.ca</p>
            
            <p>Best regards,<br>The AssisText Team</p>
            
            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
            <p style="font-size: 12px; color: #666;">
                This email was sent to {user_data.get('email')}. 
                If you did not create an account, please ignore this email.
            </p>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Welcome to AssisText!
    
    Hi {user_data.get('first_name', user_data.get('username'))}!
    
    Thank you for signing up for AssisText - your AI-powered SMS assistant platform.
    
    Account Details:
    Username: {user_data.get('username')}
    Email: {user_data.get('email')}
    Account Created: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
    
    Next Steps to Start Your 14-Day Trial:
    1. Add a Payment Method - Required for trial activation
    2. Choose Your Phone Number - Select your preferred area code
    3. Configure Your AI Assistant - Set personality and response style
    4. Start Receiving SMS - Your AI will handle messages automatically
    
    Visit https://assitext.ca/dashboard/trial-setup to get started!
    
    What You Get During Your Trial:
    - Your own dedicated SignalWire phone number
    - AI-powered SMS responses (up to 100/day)
    - Client management and conversation history
    - Business hours and auto-reply configuration
    - Real-time usage tracking and analytics
    
    If you have any questions, please contact support@assitext.ca
    
    Best regards,
    The AssisText Team
    """
    
    return send_email(user_data.get('email'), subject, html_content, text_content)


def send_trial_warning_email(user_data: Dict, days_remaining: int) -> Dict:
    """Send trial expiration warning email"""
    subject = f"Your AssisText trial expires in {days_remaining} days"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Trial Expiration Warning</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #e74c3c;">Trial Expiration Notice</h1>
            
            <p>Hi {user_data.get('first_name', user_data.get('username'))}!</p>
            
            <p>Your AssisText trial expires in <strong>{days_remaining} days</strong>.</p>
            
            <div style="background-color: #fff3cd; padding: 20px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107;">
                <h3>Don't lose access to your AI SMS assistant!</h3>
                <p>Your SignalWire phone number <strong>{user_data.get('selected_phone_number', 'N/A')}</strong> will be suspended unless you upgrade to a paid plan.</p>
                
                <h4>What happens when your trial expires:</h4>
                <ul>
                    <li>📞 Your phone number will be suspended (no incoming SMS)</li>
                    <li>🤖 AI responses will be disabled</li>
                    <li>📊 Usage tracking continues but service stops</li>
                    <li>💾 Your data and settings are preserved</li>
                </ul>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="https://assitext.ca/dashboard/billing/plans" 
                   style="background-color: #28a745; color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; display: inline-block; font-size: 16px;">
                    Choose Your Plan
                </a>
            </div>
            
            <div style="background-color: #e8f4fd; padding: 15px; border-radius: 5px;">
                <h4>🚀 Upgrade Benefits:</h4>
                <ul>
                    <li>Keep your dedicated phone number active</li>
                    <li>Unlimited AI responses (based on plan)</li>
                    <li>Advanced features and integrations</li>
                    <li>Priority customer support</li>
                </ul>
            </div>
            
            <p>Thank you for trying AssisText!</p>
            
            <p>Best regards,<br>The AssisText Team</p>
        </div>
    </body>
    </html>
    """
    
    return send_email(user_data.get('email'), subject, html_content)


def send_trial_expired_email(user_data: Dict) -> Dict:
    """Send trial expired notification"""
    subject = "Your AssisText trial has expired"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Trial Expired</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #dc3545;">Trial Expired</h1>
            
            <p>Hi {user_data.get('first_name', user_data.get('username'))}!</p>
            
            <p>Your 14-day AssisText trial has expired.</p>
            
            <div style="background-color: #f8d7da; padding: 20px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #dc3545;">
                <h3>Service Status:</h3>
                <ul>
                    <li>📞 Your phone number <strong>{user_data.get('selected_phone_number', 'N/A')}</strong> has been suspended</li>
                    <li>🤖 AI responses are disabled</li>
                    <li>📥 No new incoming SMS will be processed</li>
                    <li>💾 Your data and settings are safely preserved</li>
                </ul>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="https://assitext.ca/dashboard/billing/plans" 
                   style="background-color: #007bff; color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; display: inline-block; font-size: 16px;">
                    Reactivate Your Service
                </a>
            </div>
            
            <div style="background-color: #d1ecf1; padding: 15px; border-radius: 5px;">
                <h4>🔄 Instant Reactivation:</h4>
                <p>Choose any paid plan and your service will be reactivated immediately:</p>
                <ul>
                    <li>Your phone number will be restored</li>
                    <li>AI responses will resume</li>
                    <li>All your settings and data will be intact</li>
                </ul>
            </div>
            
            <p>We hope you enjoyed your trial and choose to continue with AssisText!</p>
            
            <p>Best regards,<br>The AssisText Team</p>
        </div>
    </body>
    </html>
    """
    
    return send_email(user_data.get('email'), subject, html_content)


def log_request(request_obj, action: str, details: Dict = None):
    """Log incoming request for debugging/analytics"""
    try:
        log_data = {
            'action': action,
            'method': request_obj.method,
            'url': request_obj.url,
            'ip_address': get_client_ip(),
            'user_agent': get_user_agent(),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if details:
            log_data['details'] = details
        
        current_app.logger.info(f"Request: {json.dumps(log_data)}")
        
    except Exception as e:
        current_app.logger.error(f"Failed to log request: {e}")


def format_phone_number(phone: str) -> str:
    """Format phone number consistently"""
    if not phone:
        return phone
    
    # Remove all non-digits
    digits = ''.join(filter(str.isdigit, phone))
    
    # Add country code if missing
    if len(digits) == 10:
        digits = '1' + digits
    
    # Format as +1-XXX-XXX-XXXX
    if len(digits) == 11 and digits.startswith('1'):
        return f"+{digits[0]}-{digits[1:4]}-{digits[4:7]}-{digits[7:]}"
    
    return phone


def sanitize_message_content(content: str, max_length: int = 1600) -> str:
    """Sanitize message content"""
    if not content:
        return ""
    
    # Remove any potentially harmful content
    content = content.strip()
    
    # Truncate if too long
    if len(content) > max_length:
        content = content[:max_length] + "..."
    
    return content


def generate_message_id() -> str:
    """Generate unique message ID"""
    return f"msg_{uuid.uuid4().hex}"


def parse_business_days(days_string: str) -> List[int]:
    """Parse business days string to list of integers"""
    if not days_string:
        return []
    
    try:
        days = [int(d.strip()) for d in days_string.split(',')]
        return [d for d in days if 1 <= d <= 7]
    except ValueError:
        return []


def validate_json_structure(data: Dict, required_fields: List[str]) -> Optional[str]:
    """Validate JSON data structure"""
    if not isinstance(data, dict):
        return "Invalid JSON structure"
    
    missing_fields = []
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
    
    if missing_fields:
        return f"Missing required fields: {', '.join(missing_fields)}"
    
    return None


def safe_json_loads(json_string: str, default=None):
    """Safely load JSON string"""
    try:
        return json.loads(json_string) if json_string else default
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(obj, default="{}"):
    """Safely dump object to JSON string"""
    try:
        return json.dumps(obj) if obj is not None else default
    except (TypeError, ValueError):
        return default


def create_trial_notification(user_id: int, notification_type: str, title: str, 
                            message: str, priority: str = 'medium') -> bool:
    """Create trial notification record"""
    try:
        from app.core.models import TrialNotification
        from app.extensions import db
        
        notification = TrialNotification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            priority=priority
        )
        
        db.session.add(notification)
        db.session.commit()
        
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to create trial notification: {e}")
        return False


# =============================================================================
# ENVIRONMENT AND CONFIGURATION HELPERS
# =============================================================================

def get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean environment variable"""
    value = os.getenv(key, '').lower()
    return value in ('true', '1', 'yes', 'on')


def get_env_int(key: str, default: int = 0) -> int:
    """Get integer environment variable"""
    try:
        return int(os.getenv(key, default))
    except (ValueError, TypeError):
        return default


def get_env_list(key: str, separator: str = ',', default: List[str] = None) -> List[str]:
    """Get list from environment variable"""
    value = os.getenv(key, '')
    if not value:
        return default or []
    
    return [item.strip() for item in value.split(separator) if item.strip()]


def is_production() -> bool:
    """Check if running in production environment"""
    return os.getenv('FLASK_ENV', '').lower() == 'production'


def is_development() -> bool:
    """Check if running in development environment"""
    return os.getenv('FLASK_ENV', '').lower() in ('development', 'dev')


def get_client_ip():
    """Get client IP address from Flask request"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr


def get_user_agent():
    """Get user agent string from Flask request"""
    return request.headers.get('User-Agent', '')
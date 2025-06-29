# app/services/signalwire_service.py - SignalWire service integration

    setup_all_signalwire_webhooks, 
    get_signalwire_phone_numbers, 
    get_signalwire_integration_status,
    configure_profile_signalwire_webhook
)
from app.models.profile import Profile
<<<<<<< HEAD
from app.utils.signalwire_helpers import get_signalwire_client, send_sms, get_signalwire_phone_numbers, get_available_phone_numbers, purchase_phone_number, configure_number_webhook, validate_signalwire_webhook_request, format_phone_display
=======
from app.models.message import Message
>>>>>>> refs/remotes/origin/main
from app.extensions import db
from app.utils.signalwire_helpers import get_signalwire_client, send_sms, get_signalwire_phone_numbers, get_available_phone_numbers, purchase_phone_number, configure_number_webhook, validate_signalwire_webhook_request, format_phone_display
from datetime import datetime
from app.utils.signalwire_helpers import get_signalwire_client, send_sms, get_signalwire_phone_numbers, get_available_phone_numbers, purchase_phone_number, configure_number_webhook, validate_signalwire_webhook_request, format_phone_display
import logging

logger = logging.getLogger(__name__)

def initialize_signalwire_integration():
    """Initialize SignalWire integration on application startup"""
    try:
        logger.info("Initializing SignalWire integration...")
        
        # Set up webhooks for all SignalWire numbers
        webhook_results = setup_all_signalwire_webhooks()
        
        # Get available phone numbers with details
        available_numbers = get_signalwire_phone_numbers()
        
        # Sync with database profiles
        sync_result = sync_signalwire_numbers_with_profiles(available_numbers)
        
        success_count = len([r for r in webhook_results if r['success']])
        
        logger.info(f"SignalWire initialization complete: {success_count} webhooks configured, {len(available_numbers)} numbers available")
        
        return {
            'success': True,
            'webhooks_configured': success_count,
            'webhook_results': webhook_results,
            'phone_numbers': available_numbers,
            'profiles_synced': sync_result['synced'],
            'profiles_created': sync_result['created']
        }
        
    except Exception as e:
        logger.error(f"SignalWire initialization failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def sync_signalwire_numbers_with_profiles(available_numbers):
    """Sync SignalWire phone numbers with profile database"""
    synced_count = 0
    created_count = 0
    
    try:
        for number_info in available_numbers:
            phone_number = number_info['phone_number']
            number_sid = number_info['sid']
            
            # Check if profile exists for this number
            existing_profile = Profile.query.filter_by(phone_number=phone_number).first()
            
            if existing_profile:
                # Update existing profile with SignalWire info
                if not existing_profile.signalwire_sid:
                    existing_profile.signalwire_sid = number_sid
                    existing_profile.webhook_status = 'active'
                    synced_count += 1
            else:
                # Could create a profile here if needed, but probably not for existing numbers
                # Just log that the number exists but has no profile
                logger.info(f"SignalWire number {phone_number} has no associated profile")
        
        if synced_count > 0:
            db.session.commit()
            logger.info(f"Synced {synced_count} profiles with SignalWire data")
        
        return {
            'synced': synced_count,
            'created': created_count
        }
        
    except Exception as e:
        logger.error(f"Error syncing SignalWire numbers with profiles: {str(e)}")
        return {
            'synced': 0,
            'created': 0
        }

def verify_signalwire_integration():
    """Verify SignalWire integration status"""
    try:
        # Check SignalWire connection
        status = get_signalwire_integration_status()
        
        if status['status'] != 'connected':
            return {
                'success': False,
                'error': f"SignalWire not connected: {status.get('error', 'Unknown error')}"
            }
        
        # Get phone numbers and check webhook configuration
        phone_numbers = get_signalwire_phone_numbers()
        
        # Check for profiles that need webhook configuration
        misconfigured_profiles = []
        profiles_with_numbers = Profile.query.filter(Profile.phone_number.isnot(None)).all()
        
        for profile in profiles_with_numbers:
            if not profile.webhook_url or profile.webhook_status != 'active':
                misconfigured_profiles.append(profile.name)
        
        return {
            'success': True,
            'status': status,
            'phone_numbers': phone_numbers,
            'misconfigured_profiles': misconfigured_profiles
        }
        
    except Exception as e:
        logger.error(f"SignalWire verification failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def get_signalwire_dashboard_data():
    """Get data for SignalWire dashboard display"""
    try:
        # Get SignalWire status
        signalwire_status = get_signalwire_integration_status()
        
        # Get phone numbers
        phone_numbers = get_signalwire_phone_numbers()
        
        # Get profiles with SignalWire integration
        profiles = Profile.query.filter(Profile.phone_number.isnot(None)).all()
        
        # Calculate statistics
        total_profiles = len(profiles)
        configured_profiles = len([p for p in profiles if p.webhook_status == 'active'])
        
        # Get recent messages (last 24 hours)
        from app.models.message import Message
        from datetime import datetime, timedelta
        
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_messages = Message.query.filter(Message.timestamp >= yesterday).count()
        
        return {
            'signalwire_status': signalwire_status,
            'phone_numbers': phone_numbers,
            'stats': {
                'total_phone_numbers': len(phone_numbers),
                'total_profiles': total_profiles,
                'configured_profiles': configured_profiles,
                'recent_messages_24h': recent_messages
            },
            'profiles': [p.to_dict() for p in profiles[:10]]  # Latest 10 profiles
        }
        
    except Exception as e:
        logger.error(f"Error getting SignalWire dashboard data: {str(e)}")
        return {
            'error': str(e),
            'signalwire_status': {'status': 'error', 'error': str(e)},
            'phone_numbers': [],
            'stats': {},
            'profiles': []
        }
def send_sms_response(to_number: str, from_number: str, message_body: str, profile_id: int) -> bool:
    """
    Send SMS response via SignalWire and log to database
    """
    try:
        client = get_signalwire_client()
        if not client:
            logger.error("SignalWire client not available")
            return False
        
        # Send SMS via SignalWire
        message = client.messages.create(
            body=message_body,
            from_=from_number,  # Your SignalWire number
            to=to_number        # User's number
        )
        
        # Log outbound message to database
        outbound_message = Message(
            profile_id=profile_id,
            from_number=from_number,
            to_number=to_number,
            message_body=message_body,
            message_sid=message.sid,
            direction='outbound',
            status='sent'
        )
        db.session.add(outbound_message)
        db.session.commit()
        
        logger.info(f"SMS sent successfully: {message.sid}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending SMS: {str(e)}")
        
        # Log failed message attempt
        try:
            failed_message = Message(
                profile_id=profile_id,
                from_number=from_number,
                to_number=to_number,
                message_body=message_body,
                direction='outbound',
                status='failed'
            )
            db.session.add(failed_message)
            db.session.commit()
        except:
            pass
        
        return False
# Re-export functions for convenience
__all__ = [
    'initialize_signalwire_integration',
    'sync_signalwire_numbers_with_profiles', 
    'verify_signalwire_integration',
    'get_signalwire_dashboard_data',
    'configure_profile_signalwire_webhook',
    'send_sms_response'
]

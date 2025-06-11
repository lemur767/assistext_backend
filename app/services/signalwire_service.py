from app.utils.signalwire_helpers import (
    setup_all_signalwire_webhooks, 
    get_signalwire_phone_numbers, 
    get_signalwire_integration_status,
    setup_signalwire_webhook_for_number
)
from app.models.profile import Profile
from app import db
from datetime import datetime
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
            
            # Find existing profile
            profile = Profile.query.filter_by(phone_number=phone_number).first()
            
            if profile:
                # Update existing profile
                profile.signalwire_number_sid = number_sid
                profile.signalwire_webhook_configured = True
                profile.signalwire_last_sync = datetime.utcnow()
                synced_count += 1
                logger.info(f"Synced existing profile '{profile.name}' with SignalWire number {phone_number}")
            else:
                # Create new profile for unassigned SignalWire number
                new_profile = Profile(
                    user_id=1,  # You might want to assign to a default admin user
                    name=f"SignalWire {phone_number}",
                    phone_number=phone_number,
                    description=f"Auto-created profile for SignalWire number {phone_number}",
                    signalwire_number_sid=number_sid,
                    signalwire_webhook_configured=True,
                    signalwire_last_sync=datetime.utcnow(),
                    ai_enabled=True  # Enable AI by default for new profiles
                )
                db.session.add(new_profile)
                created_count += 1
                logger.info(f"Created new profile for SignalWire number {phone_number}")
        
        db.session.commit()
        
        return {
            'synced': synced_count,
            'created': created_count
        }
        
    except Exception as e:
        logger.error(f"Error syncing SignalWire numbers with profiles: {str(e)}")
        db.session.rollback()
        return {
            'synced': 0,
            'created': 0,
            'error': str(e)
        }

def configure_profile_signalwire_webhook(profile_id):
    """Configure SignalWire webhook for specific profile"""
    try:
        profile = Profile.query.get(profile_id)
        if not profile:
            return {'success': False, 'error': 'Profile not found'}
        
        success, number_sid = setup_signalwire_webhook_for_number(profile.phone_number)
        
        if success:
            profile.signalwire_number_sid = number_sid
            profile.signalwire_webhook_configured = True
            profile.signalwire_last_sync = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"SignalWire webhook configured for profile {profile.name}")
            return {'success': True, 'number_sid': number_sid}
        else:
            return {'success': False, 'error': 'Failed to configure webhook'}
            
    except Exception as e:
        logger.error(f"Error configuring SignalWire webhook for profile {profile_id}: {str(e)}")
        return {'success': False, 'error': str(e)}

def verify_signalwire_integration():
    """Verify SignalWire integration is working properly"""
    try:
        status = get_signalwire_integration_status()
        
        if status['status'] == 'connected':
            logger.info("SignalWire integration verified successfully")
            
            # Check if all profiles have proper SignalWire configuration
            profiles = Profile.query.all()
            misconfigured_profiles = []
            
            for profile in profiles:
                if not profile.is_signalwire_configured():
                    misconfigured_profiles.append(profile.name)
            
            if misconfigured_profiles:
                logger.warning(f"Profiles not properly configured with SignalWire: {misconfigured_profiles}")
            
            return {
                'success': True,
                'status': status,
                'misconfigured_profiles': misconfigured_profiles
            }
        else:
            logger.error(f"SignalWire integration verification failed: {status.get('error', 'Unknown error')}")
            return {
                'success': False,
                'error': status.get('error', 'Unknown error')
            }
            
    except Exception as e:
        logger.error(f"SignalWire verification error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def get_signalwire_dashboard_data():
    """Get data for SignalWire integration dashboard"""
    try:
        # Get integration status
        status = get_signalwire_integration_status()
        
        # Get profile statistics
        total_profiles = Profile.query.count()
        configured_profiles = Profile.query.filter_by(signalwire_webhook_configured=True).count()
        active_profiles = Profile.query.filter_by(is_active=True, ai_enabled=True).count()
        
        # Get recent message statistics
        from app.models.message import Message
        from datetime import datetime, timedelta
        
        last_24h = datetime.utcnow() - timedelta(hours=24)
        recent_messages = Message.query.filter(Message.timestamp >= last_24h).count()
        recent_incoming = Message.query.filter(
            Message.timestamp >= last_24h,
            Message.is_incoming == True
        ).count()
        recent_outgoing = Message.query.filter(
            Message.timestamp >= last_24h,
            Message.is_incoming == False
        ).count()
        
        return {
            'signalwire_status': status,
            'profile_stats': {
                'total': total_profiles,
                'configured': configured_profiles,
                'active': active_profiles
            },
            'message_stats_24h': {
                'total': recent_messages,
                'incoming': recent_incoming,
                'outgoing': recent_outgoing
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting SignalWire dashboard data: {str(e)}")
        return {
            'error': str(e)
        }

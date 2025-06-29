import click
from flask.cli import with_appcontext
from app.utils.signalwire_helpers import get_signalwire_client, send_sms, get_signalwire_phone_numbers, get_available_phone_numbers, purchase_phone_number, configure_number_webhook, validate_signalwire_webhook_request, format_phone_display
from app.services.signalwire_service import (
from app.utils.signalwire_helpers import get_signalwire_client, send_sms, get_signalwire_phone_numbers, get_available_phone_numbers, purchase_phone_number, configure_number_webhook, validate_signalwire_webhook_request, format_phone_display
    initialize_signalwire_integration, 
    verify_signalwire_integration,
    get_signalwire_dashboard_data
)

@click.command()
@with_appcontext
def init_signalwire():
    """Initialize SignalWire integration"""
    click.echo("🚀 Initializing SignalWire integration...")
    result = initialize_signalwire_integration()
    
    if result['success']:
        click.echo("✅ SignalWire initialized successfully!")
        click.echo(f"📞 Webhooks configured: {result['webhooks_configured']}")
        click.echo(f"🔢 Phone numbers available: {len(result['phone_numbers'])}")
        click.echo(f"👤 Profiles synced: {result['profiles_synced']}")
        click.echo(f"🆕 Profiles created: {result['profiles_created']}")
        
        click.echo("\n📱 SignalWire Phone Numbers:")
        for number in result['phone_numbers']:
            status = "✅ Configured" if number.get('sms_url') else "❌ Not configured"
            click.echo(f"   {number['phone_number']} - {status}")
            if number.get('friendly_name'):
                click.echo(f"      Name: {number['friendly_name']}")
    else:
        click.echo(f"❌ SignalWire initialization failed: {result['error']}")

@click.command()
@with_appcontext
def verify_signalwire():
    """Verify SignalWire integration"""
    click.echo("🔍 Verifying SignalWire integration...")
    
    result = verify_signalwire_integration()
    
    if result['success']:
        click.echo("✅ SignalWire integration verified successfully!")
        
        status = result['status']
        if status['status'] == 'connected':
            click.echo(f"📡 Connected to: {status['space_url']}")
            click.echo(f"🏢 Account: {status['account']['friendly_name']}")
            click.echo(f"📞 Phone numbers: {status['phone_numbers_count']}")
            click.echo(f"🔗 Webhooks configured: {status['webhooks_configured']}")
        
        if result.get('misconfigured_profiles'):
            click.echo(f"⚠️  Profiles needing configuration: {', '.join(result['misconfigured_profiles'])}")
    else:
        click.echo(f"❌ SignalWire verification failed: {result['error']}")

@click.command()
@with_appcontext
def signalwire_status():
    """Get comprehensive SignalWire integration status"""
    click.echo("📊 SignalWire Integration Status")
    click.echo("=" * 40)
    
    dashboard_data = get_signalwire_dashboard_data()
    
    if 'error' in dashboard_data:
        click.echo(f"❌ Error getting status: {dashboard_data['error']}")
        return
    
    # SignalWire connection status
    sw_status = dashboard_data['signalwire_status']
    click.echo(f"🔌 Connection: {sw_status['status']}")
    
    if sw_status['status'] == 'connected':
        click.echo(f"🌐 Space URL: {sw_status['space_url']}")
        click.echo(f"🏢 Account: {sw_status['account']['friendly_name']} ({sw_status['account']['status']})")
        click.echo(f"📞 Phone Numbers: {sw_status['phone_numbers_count']}")
        click.echo(f"🔗 Webhooks: {sw_status['webhooks_configured']}/{sw_status['phone_numbers_count']}")
        click.echo(f"📡 Webhook URL: {sw_status['webhook_url']}")
        
        # Profile statistics
        profile_stats = dashboard_data['profile_stats']
        click.echo(f"\n👤 Profile Statistics:")
        click.echo(f"   Total profiles: {profile_stats['total']}")
        click.echo(f"   SignalWire configured: {profile_stats['configured']}")
        click.echo(f"   Active with AI: {profile_stats['active']}")
        
        # Message statistics
        msg_stats = dashboard_data['message_stats_24h']
        click.echo(f"\n💬 Messages (Last 24h):")
        click.echo(f"   Total: {msg_stats['total']}")
        click.echo(f"   Incoming: {msg_stats['incoming']}")
        click.echo(f"   Outgoing: {msg_stats['outgoing']}")
        
        # List phone numbers
        click.echo(f"\n📱 Phone Numbers:")
        for number in sw_status['phone_numbers']:
            webhook_status = "✅" if number.get('sms_url') == sw_status['webhook_url'] else "❌"
            click.echo(f"   {webhook_status} {number['phone_number']}")
            if number.get('friendly_name'):
                click.echo(f"       Name: {number['friendly_name']}")
            click.echo(f"       SMS: {'✅' if number['capabilities']['sms'] else '❌'} | "
                      f"Voice: {'✅' if number['capabilities']['voice'] else '❌'} | "
                      f"MMS: {'✅' if number['capabilities']['mms'] else '❌'}")
    else:
        click.echo(f"❌ Connection Error: {sw_status.get('error', 'Unknown error')}")

@click.command()
@with_appcontext
def test_signalwire():
    """Test SignalWire integration with a test message"""
    click.echo("🧪 Testing SignalWire integration...")
    
    # Get test phone number
    test_number = click.prompt("Enter a test phone number to send to (e.g., +15551234567)")
    test_message = "Test message from AssisText SignalWire integration! 🚀"
    
    try:
        
        # Get available numbers
        numbers = get_signalwire_phone_numbers()
        if not numbers:
            click.echo("❌ No SignalWire numbers available")
            return
        
        from_number = numbers[0]['phone_number']
        click.echo(f"📤 Sending test message from {from_number} to {test_number}")
        
        # Send test message
        result = send_signalwire_sms(from_number, test_number, test_message)
        
        click.echo(f"✅ Test message sent successfully!")
        click.echo(f"📋 Message SID: {result.sid}")
        click.echo(f"📊 Status: {result.status}")
        
    except Exception as e:
        click.echo(f"❌ Test failed: {str(e)}")

def init_app(app):
    """Register CLI commands with Flask app"""
    app.cli.add_command(init_signalwire)
    app.cli.add_command(verify_signalwire)
    app.cli.add_command(signalwire_status)
    app.cli.add_command(test_signalwire)

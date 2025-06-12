#!/usr/bin/env python3
import os
import sys

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

def main():
    print("🚀 Initializing AssisText SignalWire Integration...")
    
    try:
        # Create app
        app = create_app('production')
        
        with app.app_context():
            from app.services.signalwire_service import initialize_signalwire_integration
            
            result = initialize_signalwire_integration()
            
            if result['success']:
                print("✅ SignalWire integration initialized successfully!")
                print(f"📞 Webhooks configured: {result['webhooks_configured']}")
                print(f"🔢 Phone numbers available: {len(result['phone_numbers'])}")
                
                if result['phone_numbers']:
                    print("\n📱 SignalWire Phone Numbers:")
                    for number in result['phone_numbers']:
                        print(f"   - {number['phone_number']}")
                        
                if result.get('profiles_created', 0) > 0:
                    print(f"🆕 Created {result['profiles_created']} new profiles")
                    
            else:
                print(f"❌ SignalWire initialization failed: {result['error']}")
                sys.exit(1)
                
    except Exception as e:
        print(f"❌ Error during initialization: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()

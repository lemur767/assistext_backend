# test_create_app.py - Test the create_app function directly
import os
import sys

def test_create_app():
    """Test create_app function with detailed output"""
    print("🧪 Testing create_app function directly...")
    print("=" * 60)
    
    try:
        # Import create_app
        print("1. Importing create_app...")
        from app import create_app
        print("   ✓ create_app imported successfully")
        
        # Call create_app
        print("\n2. Calling create_app('development')...")
        app = create_app('development')
        
        # Check result
        print(f"\n3. Checking result...")
        print(f"   Result type: {type(app)}")
        print(f"   Result value: {app}")
        
        if app is None:
            print("   ❌ create_app returned None!")
            return False
        else:
            print("   ✅ create_app returned a valid app object!")
            
            # Test basic app properties
            print(f"   App name: {app.name}")
            print(f"   Debug mode: {app.debug}")
            print(f"   Config keys: {len(app.config.keys())} keys")
            
            # Test routes
            print(f"   Registered routes: {len(app.url_map._rules)} routes")
            
            return True
            
    except Exception as e:
        print(f"❌ Error testing create_app: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_app_startup():
    """Test actually starting the app"""
    print("\n🚀 Testing app startup...")
    print("=" * 30)
    
    try:
        from app import create_app
        app = create_app('development')
        
        if app is None:
            print("❌ Cannot test startup - create_app returned None")
            return False
        
        # Test app context
        with app.app_context():
            print("✅ App context works")
        
        # Test config
        print(f"✅ Secret key configured: {bool(app.config.get('SECRET_KEY'))}")
        print(f"✅ Database URI configured: {bool(app.config.get('SQLALCHEMY_DATABASE_URI'))}")
        
        return True
        
    except Exception as e:
        print(f"❌ App startup test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 SMS AI Responder - create_app Debug Test")
    print("=" * 70)
    
    # Test create_app function
    success1 = test_create_app()
    
    if success1:
        # Test app startup
        success2 = test_app_startup()
        
        if success2:
            print("\n🎉 All tests passed!")
            print("✅ Your create_app function is working correctly.")
            print("✅ You can now run: python wsgi.py")
        else:
            print("\n⚠️ create_app works but startup has issues.")
    else:
        print("\n❌ create_app function has problems.")
        print("📋 Look at the debug output above to see where it fails.")
    
    print("\n" + "=" * 70)
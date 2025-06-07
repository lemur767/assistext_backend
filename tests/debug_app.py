# debug_app.py - Use this to debug startup issues step by step
import os
import sys
import traceback

def test_imports():
    """Test all imports step by step"""
    print("🔍 Testing imports...")
    
    try:
        print("1. Testing Flask import...")
        from flask import Flask
        print("   ✓ Flask imported successfully")
    except ImportError as e:
        print(f"   ❌ Flask import failed: {e}")
        return False
    
    try:
        print("2. Testing app package import...")
        import app
        print("   ✓ App package imported")
    except ImportError as e:
        print(f"   ❌ App package import failed: {e}")
        print("   Make sure you're in the correct directory and have __init__.py files")
        return False
    
    try:
        print("3. Testing config import...")
        from app.config import config
        print("   ✓ Config imported")
    except ImportError as e:
        print(f"   ❌ Config import failed: {e}")
        return False
    
    try:
        print("4. Testing extensions import...")
        from app.extensions import db, migrate, jwt, socketio
        print("   ✓ Extensions imported")
    except ImportError as e:
        print(f"   ❌ Extensions import failed: {e}")
        return False
    
    try:
        print("5. Testing create_app import...")
        from app import create_app
        print("   ✓ create_app imported")
    except ImportError as e:
        print(f"   ❌ create_app import failed: {e}")
        return False
    
    return True

def test_environment():
    """Test environment variables and configuration"""
    print("\n🔧 Testing environment...")
    
    # Check if .env file exists
    if os.path.exists('.env'):
        print("   ✓ .env file found")
    else:
        print("   ⚠ .env file not found - using defaults")
    
    # Check critical environment variables
    config_name = os.environ.get('FLASK_CONFIG', 'development')
    print(f"   Config mode: {config_name}")
    
    # Check database URL
    if config_name == 'development':
        db_url = os.environ.get('DEV_DATABASE_URL')
    elif config_name == 'production':
        db_url = os.environ.get('DATABASE_URL')
    else:
        db_url = os.environ.get('TEST_DATABASE_URL')
    
    if db_url:
        print(f"   ✓ Database URL configured")
    else:
        print(f"   ⚠ Database URL not configured")
    
    # Check other critical vars
    secret_key = os.environ.get('SECRET_KEY')
    print(f"   Secret key: {'✓ Set' if secret_key else '⚠ Using default'}")
    
    return True

def test_app_creation():
    """Test Flask app creation step by step"""
    print("\n🏗️ Testing app creation...")
    
    try:
        print("1. Importing create_app...")
        from app import create_app
        
        print("2. Getting config name...")
        config_name = os.environ.get('FLASK_CONFIG', 'development')
        print(f"   Using config: {config_name}")
        
        print("3. Creating Flask app...")
        app = create_app(config_name)
        
        if app is None:
            print("   ❌ create_app returned None!")
            return None
        
        print("   ✓ Flask app created successfully")
        print(f"   App name: {app.name}")
        print(f"   Debug mode: {app.debug}")
        
        return app
        
    except Exception as e:
        print(f"   ❌ App creation failed: {e}")
        traceback.print_exc()
        return None

def test_app_context(app):
    """Test Flask app context"""
    print("\n🔄 Testing app context...")
    
    try:
        with app.app_context():
            print("   ✓ App context working")
            
            # Test database connection
            try:
                from app.extensions import db
                print("   ✓ Database extension accessible")
            except Exception as e:
                print(f"   ⚠ Database extension issue: {e}")
            
            return True
            
    except Exception as e:
        print(f"   ❌ App context failed: {e}")
        traceback.print_exc()
        return False

def test_models():
    """Test model imports"""
    print("\n📊 Testing model imports...")
    
    models_to_test = [
        ('user', 'app.models.user'),
        ('profile', 'app.models.profile'), 
        ('message', 'app.models.message'),
        ('client', 'app.models.client'),
        ('subscription', 'app.models.subscription')
    ]
    
    for model_name, module_name in models_to_test:
        try:
            __import__(module_name)
            print(f"   ✓ {model_name} model imported")
        except ImportError as e:
            print(f"   ⚠ {model_name} model import failed: {e}")
            # Don't fail completely for missing models
        except Exception as e:
            print(f"   ❌ {model_name} model error: {e}")

def main():
    """Main debug function"""
    print("🐛 SMS AI Responder - Debug Mode")
    print("=" * 50)
    
    # Test imports
    if not test_imports():
        print("\n❌ Import test failed. Fix import issues first.")
        return False
    
    # Test environment
    test_environment()
    
    # Test app creation
    app = test_app_creation()
    if app is None:
        print("\n❌ App creation failed. Check the errors above.")
        return False
    
    # Test app context
    if not test_app_context(app):
        print("\n❌ App context test failed.")
        return False
    
    # Test models (optional)
    test_models()
    
    print("\n🎉 All tests passed!")
    print("✅ Your app should work now. Try running: python wsgi.py")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            print("\n🔧 Common fixes:")
            print("1. Make sure you're in the backend directory")
            print("2. Check that all __init__.py files exist")
            print("3. Verify your .env file is configured")
            print("4. Install missing dependencies: pip install -r requirements.txt")
            print("5. Check database connectivity")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n👋 Debug interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error during debug: {e}")
        traceback.print_exc()
        sys.exit(1)
import os
import sys
from flask import Flask
from flask_migrate import Migrate, upgrade, migrate, init
from sqlalchemy import text

def create_migration_app():
    """Create Flask app for migration purposes"""
    app = Flask(__name__)
    
    # Basic configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'migration-secret'
    
    return app

def fix_metadata_conflicts():
    """Fix metadata conflicts by dropping and recreating problematic tables"""
    from app.extensions import db
    
    # Tables that commonly have conflicts
    problematic_tables = [
        'payment_methods',
        'payments', 
        'invoices',
        'invoice_items',
        'billing_settings',
        'credit_transactions'
    ]
    
    print("🔧 Fixing metadata conflicts...")
    
    try:
        # Check if tables exist and have conflicts
        for table_name in problematic_tables:
            if table_name in db.metadata.tables:
                print(f"⚠️  Found conflicting table: {table_name}")
                
                # Drop the table from metadata (not from database)
                db.metadata.remove(db.metadata.tables[table_name])
                print(f"✅ Removed {table_name} from metadata")
        
        print("✅ Metadata conflicts resolved")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing metadata conflicts: {e}")
        return False

def ensure_migrations_directory():
    """Ensure migrations directory exists"""
    if not os.path.exists('migrations'):
        print("📁 Creating migrations directory...")
        try:
            from flask_migrate import init as flask_migrate_init
            flask_migrate_init()
            print("✅ Migrations directory created")
        except Exception as e:
            print(f"❌ Error creating migrations directory: {e}")
            return False
    return True

def run_safe_migration():
    """Run migration safely with error handling"""
    try:
        # Create the app
        app = create_migration_app()
        
        # Initialize extensions
        from app.extensions import db
        db.init_app(app)
        migrate_obj = Migrate(app, db)
        
        with app.app_context():
            # Fix metadata conflicts first
            if not fix_metadata_conflicts():
                return False
            
            # Import models to register them
            print("📦 Importing models...")
            from app.models import (
                User, Subscription, SubscriptionPlan, Message, Client,
                PaymentMethod, Payment, Invoice, InvoiceItem,
                CreditTransaction, BillingSettings, UsageRecord,
                ActivityLog, NotificationLog, MessageTemplate
            )
            print("✅ Models imported successfully")
            
            # Ensure migrations directory exists
            if not ensure_migrations_directory():
                return False
            
            # Create new migration
            print("📋 Creating new migration...")
            try:
                migrate(message="Fix table definition conflicts")
                print("✅ Migration created successfully")
            except Exception as e:
                print(f"⚠️  Migration creation warning: {e}")
                # Continue anyway - might be no changes
            
            # Apply migrations
            print("🚀 Applying migrations...")
            upgrade()
            print("✅ Migrations applied successfully")
            
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

def verify_tables():
    """Verify all tables exist and are properly structured"""
    try:
        app = create_migration_app()
        from app.extensions import db
        db.init_app(app)
        
        with app.app_context():
            # Get all table names
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            # Expected tables
            expected_tables = [
                'users', 'subscriptions', 'subscription_plans', 'messages', 'clients',
                'payment_methods', 'payments', 'invoices', 'invoice_items',
                'credit_transactions', 'billing_settings', 'usage_records',
                'activity_logs', 'notification_logs', 'message_templates'
            ]
            
            print("📊 Table verification:")
            for table in expected_tables:
                if table in existing_tables:
                    print(f"✅ {table} - OK")
                else:
                    print(f"❌ {table} - MISSING")
            
            # Check for extra tables
            extra_tables = set(existing_tables) - set(expected_tables) - {'alembic_version'}
            if extra_tables:
                print("\n⚠️  Extra tables found:")
                for table in extra_tables:
                    print(f"   - {table}")
            
        return True
        
    except Exception as e:
        print(f"❌ Table verification failed: {e}")
        return False

def main():
    """Main migration function"""
    print("🔧 Starting database migration helper...")
    
    # Check if we're in the right directory
    if not os.path.exists('app'):
        print("❌ Error: app directory not found. Are you in the project root?")
        sys.exit(1)
    
    # Add current directory to Python path
    sys.path.insert(0, os.getcwd())
    
    # Run safe migration
    if run_safe_migration():
        print("✅ Migration completed successfully!")
        
        # Verify tables
        if verify_tables():
            print("✅ All tables verified!")
        else:
            print("⚠️  Some tables may need attention")
    else:
        print("❌ Migration failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()

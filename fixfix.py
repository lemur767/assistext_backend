#!/usr/bin/env python3
"""
Alembic Version Fix Script
Fixes the "Can't locate revision identified by 'restructure_profiles_001'" error
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

def print_status(message, status="INFO"):
    """Print status message"""
    symbols = {"SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️"}
    symbol = symbols.get(status, "•")
    print(f"{symbol} {message}")

def get_database_url():
    """Get database URL from environment"""
    return os.getenv('DATABASE_URL','postgresql://app_user:Assistext2025Secure@localhost/assistext_prod')

def check_alembic_version_table(engine):
    """Check what's in the alembic_version table"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            current_version = result.fetchone()
            if current_version:
                print_status(f"Current alembic version: {current_version[0]}", "INFO")
                return current_version[0]
            else:
                print_status("No version found in alembic_version table", "WARNING")
                return None
    except SQLAlchemyError as e:
        print_status(f"Error checking alembic_version table: {e}", "ERROR")
        return None

def update_alembic_version(engine, new_version):
    """Update the alembic_version table to point to a valid revision"""
    try:
        with engine.connect() as conn:
            # Check if table exists and has data
            result = conn.execute(text("SELECT COUNT(*) FROM alembic_version"))
            count = result.fetchone()[0]
            
            if count > 0:
                # Update existing version
                conn.execute(text("UPDATE alembic_version SET version_num = :version"), 
                           {"version": new_version})
                print_status(f"Updated alembic_version to {new_version}", "SUCCESS")
            else:
                # Insert new version
                conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:version)"), 
                           {"version": new_version})
                print_status(f"Inserted alembic_version {new_version}", "SUCCESS")
            
            # Commit the transaction
            conn.commit()
            return True
            
    except SQLAlchemyError as e:
        print_status(f"Error updating alembic_version: {e}", "ERROR")
        return False

def get_latest_migration_revision():
    """Get the latest migration revision from files"""
    migrations_dir = "migrations/versions"
    if not os.path.exists(migrations_dir):
        print_status("No migrations directory found", "ERROR")
        return None
    
    # Your current migrations based on the files I saw
    available_revisions = {
        "d2f924302c45": "initial_migrate",
        "48feed60906d": "fixed_meta"
    }
    
    print_status("Available migration revisions:", "INFO")
    for rev, name in available_revisions.items():
        print(f"  - {rev}: {name}")
    
    # Return the latest one (fixed_meta)
    return "48feed60906d"

def fix_alembic_version():
    """Main fix function"""
    print_status("🔧 Fixing alembic_version table...", "INFO")
    
    # Get database URL
    db_url = get_database_url()
    if not db_url:
        print_status("DATABASE_URL not found in environment", "ERROR")
        return False
    
    try:
        # Create engine
        engine = create_engine(db_url)
        print_status("Connected to database", "SUCCESS")
        
        # Check current version
        current_version = check_alembic_version_table(engine)
        
        if current_version == "restructure_profiles_001":
            print_status("Found problematic revision: restructure_profiles_001", "WARNING")
            
            # Get latest valid revision
            latest_revision = get_latest_migration_revision()
            if not latest_revision:
                return False
            
            print_status(f"Will update to latest revision: {latest_revision}", "INFO")
            
            # Update the alembic_version table
            if update_alembic_version(engine, latest_revision):
                print_status("✅ Alembic version fixed successfully!", "SUCCESS")
                return True
            else:
                return False
        
        elif current_version in ["d2f924302c45", "48feed60906d"]:
            print_status("Alembic version looks correct", "SUCCESS")
            return True
        
        elif current_version is None:
            print_status("No alembic version found, will set to latest", "INFO")
            latest_revision = get_latest_migration_revision()
            if latest_revision and update_alembic_version(engine, latest_revision):
                print_status("✅ Alembic version set successfully!", "SUCCESS")
                return True
            else:
                return False
        
        else:
            print_status(f"Unknown revision: {current_version}", "WARNING")
            print_status("Will update to latest known revision", "INFO")
            latest_revision = get_latest_migration_revision()
            if latest_revision and update_alembic_version(engine, latest_revision):
                print_status("✅ Alembic version updated successfully!", "SUCCESS")
                return True
            else:
                return False
    
    except Exception as e:
        print_status(f"Unexpected error: {e}", "ERROR")
        return False

def verify_fix():
    """Verify the fix worked"""
    print_status("🔍 Verifying fix...", "INFO")
    
    try:
        db_url = get_database_url()
        engine = create_engine(db_url)
        
        current_version = check_alembic_version_table(engine)
        if current_version in ["d2f924302c45", "48feed60906d"]:
            print_status("✅ Fix verified - alembic version is now valid!", "SUCCESS")
            return True
        else:
            print_status("❌ Fix verification failed", "ERROR")
            return False
    
    except Exception as e:
        print_status(f"Error verifying fix: {e}", "ERROR")
        return False

def main():
    """Main function"""
    print("🔧 Alembic Version Fix Script")
    print("=" * 50)
    print("This script fixes the 'Can't locate revision restructure_profiles_001' error")
    print("=" * 50)
    
    # Check if we have database URL
    if not get_database_url():
        print_status("Please set DATABASE_URL environment variable", "ERROR")
        sys.exit(1)
    
    # Fix the alembic version
    if fix_alembic_version():
        # Verify the fix
        if verify_fix():
            print("\n" + "=" * 50)
            print_status("🎯 Next Steps:", "SUCCESS")
            print("   1. Run: flask db upgrade")
            print("   2. Then: flask db migrate -m 'Fix table conflicts'")
            print("   3. Finally: flask db upgrade")
            print("   4. Test your application: python wsgi.py")
            print("=" * 50)
        else:
            print_status("Fix verification failed - manual intervention may be needed", "ERROR")
    else:
        print_status("Fix failed - see errors above", "ERROR")
        print("\n📋 Manual fix option:")
        print("   Connect to your database and run:")
        print("   UPDATE alembic_version SET version_num = '48feed60906d';")

if __name__ == '__main__':
    main()

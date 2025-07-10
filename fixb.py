#!/usr/bin/env python3
"""
Complete Migration Reset Script
Fixes corrupted migration state by resetting everything
"""
import os
import sys
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

def print_status(message, status="INFO"):
    """Print status message"""
    symbols = {"SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️"}
    symbol = symbols.get(status, "•")
    print(f"{symbol} {message}")

def run_command(cmd, capture_output=True):
    """Run a shell command"""
    env = os.environ.copy()
    env['FLASK_APP'] = 'wsgi.py'
    
    try:
        if capture_output:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
            return result.returncode == 0, result.stdout, result.stderr
        else:
            result = subprocess.run(cmd, shell=True, env=env)
            return result.returncode == 0, "", ""
    except Exception as e:
        return False, "", str(e)

def backup_current_state():
    """Backup current migrations and database state"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Backup migrations directory
    if os.path.exists('migrations'):
        backup_dir = f"migrations_backup_{timestamp}"
        shutil.copytree('migrations', backup_dir)
        print_status(f"Migrations backed up to {backup_dir}", "SUCCESS")
        return backup_dir
    else:
        print_status("No migrations directory to backup", "INFO")
        return None

def clean_alembic_version_table():
    """Clean the alembic_version table"""
    print_status("Cleaning alembic_version table...", "INFO")
    
    try:
        from app import create_app
        from app.extensions import db
        
        app = create_app()
        with app.app_context():
            # Drop alembic_version table if it exists
            db.engine.execute("DROP TABLE IF EXISTS alembic_version CASCADE")
            print_status("Dropped alembic_version table", "SUCCESS")
            return True
    except Exception as e:
        print_status(f"Error cleaning alembic_version table: {e}", "ERROR")
        return False

def remove_migrations_directory():
    """Remove the corrupted migrations directory"""
    if os.path.exists('migrations'):
        try:
            shutil.rmtree('migrations')
            print_status("Removed corrupted migrations directory", "SUCCESS")
            return True
        except Exception as e:
            print_status(f"Error removing migrations directory: {e}", "ERROR")
            return False
    return True

def initialize_fresh_migrations():
    """Initialize fresh migrations"""
    print_status("Initializing fresh migrations...", "INFO")
    
    success, stdout, stderr = run_command("flask db init")
    if success:
        print_status("Flask-Migrate initialized successfully", "SUCCESS")
        return True
    else:
        print_status(f"Flask-Migrate initialization failed: {stderr}", "ERROR")
        return False

def create_initial_migration():
    """Create initial migration with all current models"""
    print_status("Creating initial migration...", "INFO")
    
    success, stdout, stderr = run_command("flask db migrate -m 'Initial migration - fresh start'")
    if success:
        print_status("Initial migration created successfully", "SUCCESS")
        print("Migration output:")
        print(stdout)
        return True
    else:
        print_status(f"Migration creation failed: {stderr}", "ERROR")
        return False

def apply_migration():
    """Apply the migration to database"""
    print_status("Applying migration to database...", "INFO")
    
    success, stdout, stderr = run_command("flask db upgrade")
    if success:
        print_status("Migration applied successfully", "SUCCESS")
        return True
    else:
        print_status(f"Migration application failed: {stderr}", "ERROR")
        return False

def validate_migration_state():
    """Validate that migration state is now correct"""
    print_status("Validating migration state...", "INFO")
    
    # Check current migration
    success, stdout, stderr = run_command("flask db current")
    if success:
        current = stdout.strip()
        if current:
            print_status(f"Current migration: {current}", "SUCCESS")
            return True
        else:
            print_status("No current migration found", "ERROR")
            return False
    else:
        print_status(f"Could not check current migration: {stderr}", "ERROR")
        return False

def test_application():
    """Test that the application can start"""
    print_status("Testing application startup...", "INFO")
    
    try:
        from app import create_app
        app = create_app()
        if app:
            print_status("Application created successfully", "SUCCESS")
            return True
        else:
            print_status("Application creation failed", "ERROR")
            return False
    except Exception as e:
        print_status(f"Application test failed: {e}", "ERROR")
        return False

def main():
    """Main reset function"""
    print("🔥 Complete Migration Reset Script")
    print("=" * 60)
    print("⚠️  WARNING: This will completely reset your migration state!")
    print("⚠️  Make sure you have backed up your database!")
    print("=" * 60)
    
    # Confirm with user
    response = input("\nDo you want to proceed with complete migration reset? (type 'yes'): ")
    if response.lower() != 'yes':
        print_status("Migration reset cancelled", "INFO")
        sys.exit(0)
    
    # Check environment
    if not os.path.exists('app'):
        print_status("Error: app directory not found. Are you in the project root?", "ERROR")
        sys.exit(1)
    
    print_status("Starting complete migration reset...", "INFO")
    
    # Step 1: Backup current state
    backup_dir = backup_current_state()
    
    # Step 2: Clean alembic_version table
    if not clean_alembic_version_table():
        print_status("Failed to clean alembic_version table - continuing anyway", "WARNING")
    
    # Step 3: Remove migrations directory
    if not remove_migrations_directory():
        print_status("Failed to remove migrations directory", "ERROR")
        sys.exit(1)
    
    # Step 4: Initialize fresh migrations
    if not initialize_fresh_migrations():
        print_status("Failed to initialize migrations", "ERROR")
        sys.exit(1)
    
    # Step 5: Create initial migration
    if not create_initial_migration():
        print_status("Failed to create initial migration", "ERROR")
        
        # Show detailed error info
        print("\n🔍 Detailed error diagnosis:")
        success, stdout, stderr = run_command("flask db migrate -m 'Debug migration'")
        print(f"STDOUT: {stdout}")
        print(f"STDERR: {stderr}")
        sys.exit(1)
    
    # Step 6: Apply migration
    if not apply_migration():
        print_status("Failed to apply migration", "ERROR")
        sys.exit(1)
    
    # Step 7: Validate migration state
    if not validate_migration_state():
        print_status("Migration state validation failed", "ERROR")
        sys.exit(1)
    
    # Step 8: Test application
    if not test_application():
        print_status("Application test failed", "ERROR")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print_status("🎉 Complete migration reset successful!", "SUCCESS")
    print_status("Your migration state has been completely reset and is now clean", "SUCCESS")
    
    if backup_dir:
        print_status(f"Your old migrations are backed up in: {backup_dir}", "INFO")
    
    print("\n🎯 Next Steps:")
    print("   1. Test your application: python wsgi.py")
    print("   2. If everything works, you can delete the backup directory")
    print("   3. Future migrations will work normally with: flask db migrate")
    print("=" * 60)

if __name__ == '__main__':
    main()

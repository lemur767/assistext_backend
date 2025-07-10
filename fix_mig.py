#!/usr/bin/env python3
"""
Migration Fix Script - Resolves "Target database is not up to date" error
This script will fix your existing migration issues
"""
import os
import sys
import subprocess
from datetime import datetime

def print_status(message, status="INFO"):
    """Print status message"""
    symbols = {"SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️"}
    symbol = symbols.get(status, "•")
    print(f"{symbol} {message}")

def run_command(cmd, cwd=None):
    """Run a shell command and return result"""
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def check_migration_status():
    """Check current migration status"""
    print_status("Checking migration status...")
    
    # Check if migrations directory exists
    if not os.path.exists('migrations'):
        print_status("No migrations directory found", "ERROR")
        return False
    
    # Check current migration
    success, stdout, stderr = run_command("flask db current")
    if success:
        print_status(f"Current migration: {stdout.strip()}", "INFO")
        return True
    else:
        print_status(f"Could not check current migration: {stderr}", "ERROR")
        return False

def show_migration_history():
    """Show migration history"""
    print_status("Showing migration history...")
    
    success, stdout, stderr = run_command("flask db history")
    if success:
        print("Migration History:")
        print(stdout)
    else:
        print_status(f"Could not show history: {stderr}", "WARNING")

def upgrade_database():
    """Try to upgrade database to latest migration"""
    print_status("Attempting to upgrade database...")
    
    success, stdout, stderr = run_command("flask db upgrade")
    if success:
        print_status("Database upgraded successfully", "SUCCESS")
        return True
    else:
        print_status(f"Database upgrade failed: {stderr}", "ERROR")
        return False

def stamp_database_as_current():
    """Stamp the database as current (if manual fixes were made)"""
    print_status("Stamping database as current...")
    
    success, stdout, stderr = run_command("flask db stamp head")
    if success:
        print_status("Database stamped as current", "SUCCESS")
        return True
    else:
        print_status(f"Database stamp failed: {stderr}", "ERROR")
        return False

def create_new_migration():
    """Create a new migration for any pending changes"""
    print_status("Creating new migration for pending changes...")
    
    success, stdout, stderr = run_command("flask db migrate -m 'Fix table definition conflicts'")
    if success:
        print_status("New migration created successfully", "SUCCESS")
        print(stdout)
        return True
    else:
        print_status(f"Migration creation failed: {stderr}", "ERROR")
        return False

def reset_migrations():
    """Reset migrations completely (DANGEROUS - will lose data if not backed up)"""
    print_status("⚠️  DANGER: Resetting migrations completely!", "WARNING")
    
    response = input("This will reset all migrations. Are you sure? (type 'yes' to confirm): ")
    if response.lower() != 'yes':
        print_status("Migration reset cancelled", "INFO")
        return False
    
    print_status("Backing up current migrations...", "INFO")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = f"migrations_backup_{timestamp}"
    
    # Backup migrations
    success, stdout, stderr = run_command(f"cp -r migrations {backup_dir}")
    if success:
        print_status(f"Migrations backed up to {backup_dir}", "SUCCESS")
    else:
        print_status("Could not backup migrations", "ERROR")
        return False
    
    # Remove migrations directory
    success, stdout, stderr = run_command("rm -rf migrations")
    if not success:
        print_status("Could not remove migrations directory", "ERROR")
        return False
    
    # Initialize new migrations
    success, stdout, stderr = run_command("flask db init")
    if not success:
        print_status(f"Could not initialize migrations: {stderr}", "ERROR")
        return False
    
    print_status("Migrations directory reset", "SUCCESS")
    return True

def main():
    """Main function"""
    print("🔧 Migration Fix Script")
    print("=" * 50)
    
    # Set environment variables
    os.environ['FLASK_APP'] = 'wsgi.py'
    
    # Check if we're in the right directory
    if not os.path.exists('app'):
        print_status("Error: app directory not found. Are you in the project root?", "ERROR")
        sys.exit(1)
    
    # Step 1: Check current migration status
    has_migrations = check_migration_status()
    
    if has_migrations:
        # Step 2: Show migration history
        show_migration_history()
        
        # Step 3: Try to upgrade database
        if upgrade_database():
            print_status("✅ Database is now up to date!", "SUCCESS")
            
            # Step 4: Create new migration if needed
            if create_new_migration():
                print_status("Created new migration for any pending changes", "SUCCESS")
                
                # Step 5: Apply the new migration
                if upgrade_database():
                    print_status("✅ All migrations applied successfully!", "SUCCESS")
                else:
                    print_status("Could not apply new migration", "ERROR")
            else:
                print_status("No new changes to migrate", "INFO")
        else:
            print_status("Database upgrade failed. Trying alternative solutions...", "WARNING")
            
            # Alternative 1: Stamp database as current
            print("\n🔄 Alternative 1: Stamp database as current")
            if stamp_database_as_current():
                print_status("Database stamped successfully", "SUCCESS")
                
                # Try creating new migration
                if create_new_migration():
                    if upgrade_database():
                        print_status("✅ Fixed with stamp method!", "SUCCESS")
                    else:
                        print_status("Still having issues after stamping", "ERROR")
            else:
                print_status("Stamp method failed", "ERROR")
                
                # Alternative 2: Reset migrations
                print("\n🔄 Alternative 2: Reset migrations (DANGEROUS)")
                print("This will:")
                print("- Backup your current migrations")
                print("- Delete the migrations directory")
                print("- Create a fresh migrations setup")
                print("- ⚠️  You may lose data if not backed up properly!")
                
                if reset_migrations():
                    print_status("Creating fresh migration...", "INFO")
                    if create_new_migration():
                        if upgrade_database():
                            print_status("✅ Fixed with reset method!", "SUCCESS")
                        else:
                            print_status("Still having issues after reset", "ERROR")
                    else:
                        print_status("Could not create fresh migration", "ERROR")
    else:
        print_status("No migrations found, creating fresh setup...", "INFO")
        
        # Initialize migrations
        success, stdout, stderr = run_command("flask db init")
        if success:
            print_status("Migrations initialized", "SUCCESS")
            
            # Create initial migration
            if create_new_migration():
                if upgrade_database():
                    print_status("✅ Fresh setup completed!", "SUCCESS")
                else:
                    print_status("Could not apply initial migration", "ERROR")
            else:
                print_status("Could not create initial migration", "ERROR")
        else:
            print_status(f"Could not initialize migrations: {stderr}", "ERROR")
    
    print("\n" + "=" * 50)
    print_status("🎯 Next Steps:", "INFO")
    print("   1. Test your application: python wsgi.py")
    print("   2. Check database tables exist properly")
    print("   3. If issues persist, check the migration files in migrations/versions/")
    print("=" * 50)

if __name__ == '__main__':
    main()

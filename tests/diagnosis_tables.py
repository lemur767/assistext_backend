#!/usr/bin/env python3
"""
SQLAlchemy Diagnostic Script
Run this to identify what's causing the table conflict
"""

import sys
import os
from sqlalchemy import MetaData

def diagnose_table_conflict():
    """Diagnose what's causing the SQLAlchemy table conflict"""
    
    print("=== SQLAlchemy Table Conflict Diagnostic ===\n")
    
    # Check current working directory
    print(f"Current working directory: {os.getcwd()}")
    print(f"Python path: {sys.path[:3]}...")  # Show first 3 entries
    
    # Check if we can import app modules
    try:
        print("\n1. Testing basic app import...")
        from app.extensions import db
        print("✓ Successfully imported db from extensions")
    except Exception as e:
        print(f"✗ Failed to import db: {e}")
        return
    
    # Check MetaData before importing models
    print(f"\n2. MetaData tables before importing models: {list(db.metadata.tables.keys())}")
    
    # Try importing models one by one
    models = ['user', 'profile', 'subscription', 'client', 'message']
    
    for model_name in models:
        try:
            print(f"\n3. Importing {model_name} model...")
            exec(f"from app.models.{model_name} import *")
            print(f"✓ Successfully imported {model_name}")
            print(f"   Tables now: {list(db.metadata.tables.keys())}")
        except Exception as e:
            print(f"✗ Failed to import {model_name}: {e}")
            print(f"   Error type: {type(e).__name__}")
            
            # If this is the subscription error, show more detail
            if 'subscriptions' in str(e).lower():
                print(f"   >>> This is the problematic import! <<<")
                print(f"   Current tables in metadata: {list(db.metadata.tables.keys())}")
                
                # Check if table already exists
                if 'subscriptions' in db.metadata.tables:
                    table = db.metadata.tables['subscriptions']
                    print(f"   Existing 'subscriptions' table info:")
                    print(f"   - Columns: {[c.name for c in table.columns]}")
                    print(f"   - Module: {table.__module__ if hasattr(table, '__module__') else 'Unknown'}")
                
                break
    
    print(f"\n4. Final MetaData tables: {list(db.metadata.tables.keys())}")
    
    # Check for duplicate imports
    print(f"\n5. Checking sys.modules for duplicates...")
    app_modules = [name for name in sys.modules.keys() if name.startswith('app.models')]
    for module in sorted(app_modules):
        print(f"   - {module}")
    
    print("\n=== End Diagnostic ===")

if __name__ == "__main__":
    # Set up environment
    os.environ.setdefault('FLASK_APP', 'wsgi.py')
    
    try:
        diagnose_table_conflict()
    except Exception as e:
        print(f"Diagnostic failed: {e}")
        import traceback
        traceback.print_exc()
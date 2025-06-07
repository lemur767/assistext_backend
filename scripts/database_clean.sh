#!/bin/bash

# Database cleanup script to fix SQLAlchemy table conflicts

echo "Cleaning up database and migrations..."

# Remove existing migrations (if you're comfortable starting fresh)
rm -rf migrations/

# Remove any .pyc files that might be causing import issues
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +

# Reinitialize the database
export FLASK_APP=wsgi.py

echo "Initializing Flask-Migrate..."
flask db init

echo "Creating initial migration..."
flask db migrate -m "Initial migration with all models"

echo "Applying migration..."
flask db upgrade

echo "Database cleanup complete!"
echo ""
echo "If you still get errors, you may need to:"
echo "1. Drop your database entirely and recreate it"
echo "2. Check for duplicate model definitions"
echo "3. Ensure all model files have proper imports"

#!/bin/bash

echo "=== Installing SMS AI Responder Dependencies ==="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# Verify critical packages
echo ""
echo "Verifying installation..."
python -c "
import flask
import flask_cors
import flask_sqlalchemy
import flask_migrate
import flask_jwt_extended
import flask_socketio
import celery
import redis
import twilio
import openai
import stripe
print('✅ All critical packages installed successfully!')
"

echo ""
echo "=== Installation Complete ==="
echo ""
echo "To activate the virtual environment in the future, run:"
echo "source venv/bin/activate"
echo ""
echo "Next steps:"
echo "1. Configure your .env file"
echo "2. Set up your database"
echo "3. Run flask db init && flask db migrate && flask db upgrade"
echo "4. Start the application with: flask run"

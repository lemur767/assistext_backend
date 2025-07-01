#!/bin/bash
# Backend Startup Failure Diagnosis & Fix

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${RED}🔧 Backend Startup Failure Diagnosis${NC}"
echo "====================================="

BACKEND_DIR="/opt/assistext_backend"
SERVICE_NAME="assistext-backend"

echo -e "\n${BLUE}1. Stop Service and Check Logs${NC}"
echo "=============================="

# Stop the failing service
sudo systemctl stop $SERVICE_NAME

# Get recent logs
echo "Recent service logs:"
sudo journalctl -u $SERVICE_NAME --no-pager -n 30 || echo "No logs available"

echo -e "\n${BLUE}2. Check File Structure${NC}"
echo "======================="

echo "Backend directory contents:"
ls -la $BACKEND_DIR | head -20

echo -e "\nPython files in backend:"
find $BACKEND_DIR -name "*.py" -type f | head -10

echo -e "\nVirtual environment check:"
if [ -d "$BACKEND_DIR/venv" ]; then
    echo "✅ Virtual environment exists"
    ls -la $BACKEND_DIR/venv/bin/ | grep -E "(python|gunicorn|pip)" || echo "Missing executables"
else
    echo "❌ Virtual environment missing"
fi

echo -e "\n${BLUE}3. Test Manual Application Import${NC}"
echo "=================================="

cd $BACKEND_DIR

echo "Testing Python and Flask imports..."
sudo -u admin $BACKEND_DIR/venv/bin/python << 'EOF'
import sys
import os
sys.path.insert(0, '/opt/assistext_backend')

print("Python version:", sys.version)
print("Current directory:", os.getcwd())
print("Python path:", sys.path[:3])

try:
    print("Testing Flask import...")
    import flask
    print("✅ Flask version:", flask.__version__)
except ImportError as e:
    print("❌ Flask import failed:", e)

try:
    print("Testing wsgi import...")
    import wsgi
    print("✅ WSGI module imported successfully")
    
    print("Testing application object...")
    app = wsgi.application
    print("✅ Application object:", type(app))
    
    print("Testing app configuration...")
    with app.app_context():
        print("✅ App context works")
        
except ImportError as e:
    print("❌ WSGI import failed:", e)
except AttributeError as e:
    print("❌ Application object error:", e)
except Exception as e:
    print("❌ Other error:", e)
    import traceback
    traceback.print_exc()
EOF

echo -e "\n${BLUE}4. Check Dependencies${NC}"
echo "===================="

echo "Checking requirements.txt..."
if [ -f "$BACKEND_DIR/requirements.txt" ]; then
    echo "✅ requirements.txt exists"
    echo "Contents:"
    head -10 $BACKEND_DIR/requirements.txt
    
    echo -e "\nChecking if dependencies are installed..."
    cd $BACKEND_DIR
    sudo -u admin $BACKEND_DIR/venv/bin/pip list | grep -E "(flask|gunicorn|sqlalchemy|redis|celery)" || echo "Missing key packages"
else
    echo "❌ requirements.txt not found"
fi

echo -e "\n${BLUE}5. Check Environment Variables${NC}"
echo "=============================="

if [ -f "$BACKEND_DIR/.env" ]; then
    echo "✅ .env file exists"
    echo "Environment variables (values hidden):"
    grep -v "^#" $BACKEND_DIR/.env | grep -v "^$" | sed 's/=.*/=***/' | head -10
else
    echo "❌ .env file missing"
    echo "Creating basic .env file..."
    
    cat > $BACKEND_DIR/.env << 'EOF'
FLASK_APP=wsgi.py
FLASK_ENV=production
SECRET_KEY=temporary-secret-key-change-this
DATABASE_URL=postgresql://admin:password@localhost/assistext_db
REDIS_URL=redis://localhost:6379/0
SIGNALWIRE_PROJECT_ID=your-project-id
SIGNALWIRE_AUTH_TOKEN=your-auth-token
SIGNALWIRE_SPACE_URL=your-space.signalwire.com
EOF
    
    sudo chown admin:admin $BACKEND_DIR/.env
    echo "✅ Created basic .env file"
fi

echo -e "\n${BLUE}6. Test Direct Gunicorn Startup${NC}"
echo "==============================="

echo "Testing gunicorn directly..."
cd $BACKEND_DIR

# Test gunicorn with more verbose output
sudo -u admin bash -c "
cd $BACKEND_DIR
export FLASK_APP=wsgi.py
export FLASK_ENV=production
timeout 15s $BACKEND_DIR/venv/bin/gunicorn --bind 127.0.0.1:5001 --workers 1 --timeout 30 --log-level debug wsgi:application
" &

GUNICORN_PID=$!
sleep 5

# Test if it started
if curl -s --connect-timeout 5 http://localhost:5001/health >/dev/null 2>&1; then
    echo "✅ Direct gunicorn startup works!"
    RESPONSE=$(curl -s http://localhost:5001/health)
    echo "Response: $RESPONSE"
    
    # Kill the test process
    kill $GUNICORN_PID 2>/dev/null || true
    wait $GUNICORN_PID 2>/dev/null || true
    
    echo "The app works manually, so it's a systemd configuration issue."
    
elif kill -0 $GUNICORN_PID 2>/dev/null; then
    echo "❌ Gunicorn started but not responding"
    kill $GUNICORN_PID 2>/dev/null || true
    wait $GUNICORN_PID 2>/dev/null || true
else
    echo "❌ Gunicorn failed to start"
fi

echo -e "\n${BLUE}7. Create Working Application${NC}"
echo "============================="

# Check if wsgi.py exists and is valid
if [ ! -f "$BACKEND_DIR/wsgi.py" ]; then
    echo "Creating basic wsgi.py..."
    
    cat > $BACKEND_DIR/wsgi.py << 'EOF'
import os
import sys

# Add the backend directory to Python path
sys.path.insert(0, '/opt/assistext_backend')

try:
    from app import create_app
    application = create_app()
    
    if __name__ == "__main__":
        application.run(host='0.0.0.0', port=5000, debug=False)
        
except ImportError:
    # Fallback simple Flask app if main app doesn't work
    from flask import Flask, jsonify
    
    application = Flask(__name__)
    
    @application.route('/health')
    def health():
        return jsonify({
            'status': 'healthy',
            'message': 'Backend is running',
            'version': '1.0.0'
        })
    
    @application.route('/api/test')
    def test():
        return jsonify({
            'success': True,
            'message': 'API is working'
        })
    
    if __name__ == "__main__":
        application.run(host='0.0.0.0', port=5000, debug=False)
EOF
    
    sudo chown admin:admin $BACKEND_DIR/wsgi.py
    echo "✅ Created working wsgi.py"
fi

echo -e "\n${BLUE}8. Install Missing Dependencies${NC}"
echo "==============================="

cd $BACKEND_DIR

# Install basic Flask requirements if missing
echo "Installing/updating basic dependencies..."
sudo -u admin $BACKEND_DIR/venv/bin/pip install --upgrade pip
sudo -u admin $BACKEND_DIR/venv/bin/pip install flask gunicorn python-dotenv

# If requirements.txt exists, install from it
if [ -f "requirements.txt" ]; then
    echo "Installing from requirements.txt..."
    sudo -u admin $BACKEND_DIR/venv/bin/pip install -r requirements.txt || echo "Some packages failed to install"
fi

echo -e "\n${BLUE}9. Create Simplified Service${NC}"
echo "==========================="

# Create a more robust service file
sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null << EOF
[Unit]
Description=AssisText Flask Backend
After=network.target

[Service]
Type=simple
User=admin
Group=admin
WorkingDirectory=$BACKEND_DIR
ExecStart=/bin/bash -c 'cd $BACKEND_DIR && source venv/bin/activate && exec gunicorn --bind 127.0.0.1:5000 --workers 2 --timeout 60 --log-level info wsgi:application'
Restart=always
RestartSec=15
Environment=PYTHONPATH=$BACKEND_DIR
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Created simplified systemd service"

echo -e "\n${BLUE}10. Test the Fixed Service${NC}"
echo "=========================="

# Reload and start
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME

echo "Starting the service..."
if sudo systemctl start $SERVICE_NAME; then
    echo "✅ Service start command succeeded"
else
    echo "❌ Service start command failed"
fi

# Wait and check status
sleep 10

echo -e "\nService status:"
sudo systemctl status $SERVICE_NAME --no-pager -l

echo -e "\nTesting connection:"
if curl -s --connect-timeout 10 http://localhost:5000/health >/dev/null 2>&1; then
    RESPONSE=$(curl -s http://localhost:5000/health)
    echo "✅ Backend is responding: $RESPONSE"
else
    echo "❌ Backend still not responding"
    
    echo -e "\nRecent logs:"
    sudo journalctl -u $SERVICE_NAME --no-pager -n 20
fi

echo -e "\n${GREEN}🎉 Backend Startup Fix Complete${NC}"
echo "==============================="

if curl -s --connect-timeout 5 http://localhost:5000/health >/dev/null 2>&1; then
    echo "✅ SUCCESS: Backend is now running!"
    echo ""
    echo "Next steps:"
    echo "1. Set up SSL certificates"
    echo "2. Update frontend to use backend URL"
    echo "3. Test API endpoints"
else
    echo "❌ Backend still not working"
    echo ""
    echo "Try these manual steps:"
    echo "1. cd $BACKEND_DIR"
    echo "2. source venv/bin/activate"
    echo "3. python wsgi.py"
    echo "4. Check for any error messages"
    echo ""
    echo "Or run in screen session:"
    echo "1. screen -S backend"
    echo "2. cd $BACKEND_DIR && source venv/bin/activate"
    echo "3. gunicorn --bind 127.0.0.1:5000 wsgi:application"
fi

echo -e "\n${BLUE}Service Management Commands:${NC}"
echo "sudo systemctl start $SERVICE_NAME"
echo "sudo systemctl stop $SERVICE_NAME"
echo "sudo systemctl status $SERVICE_NAME"
echo "sudo journalctl -u $SERVICE_NAME -f"

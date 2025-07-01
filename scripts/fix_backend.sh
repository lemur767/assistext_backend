#!/bin/bash
# Fix Systemd Namespace Error 226

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${RED}🔧 Fixing Systemd Namespace Error 226${NC}"
echo "====================================="

SERVICE_NAME="assistext-backend"
BACKEND_DIR="/opt/assistext_backend"

echo "Error 226/NAMESPACE means systemd security settings are too restrictive."
echo "We'll create a simpler service file without problematic security features."

echo -e "\n${BLUE}1. Stop Current Service${NC}"
echo "======================"

sudo systemctl stop $SERVICE_NAME 2>/dev/null || echo "Service was not running"

echo -e "\n${BLUE}2. Create Simple Service File${NC}"
echo "============================="

echo "Creating new simplified service file..."

sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=AssisText Flask Backend
After=network.target

[Service]
Type=simple
User=admin
Group=admin
WorkingDirectory=${BACKEND_DIR}
Environment=PATH=${BACKEND_DIR}/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=FLASK_APP=wsgi.py
Environment=FLASK_ENV=production
EnvironmentFile=-${BACKEND_DIR}/.env
ExecStart=${BACKEND_DIR}/venv/bin/gunicorn --bind 127.0.0.1:5000 --workers 2 --timeout 60 wsgi:application
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Created simplified service file (removed security restrictions)"

echo -e "\n${BLUE}3. Fix Permissions${NC}"
echo "=================="

echo "Ensuring proper ownership..."
sudo chown -R admin:admin ${BACKEND_DIR}

echo "Making scripts executable..."
sudo chmod +x ${BACKEND_DIR}/venv/bin/* 2>/dev/null || true

echo "Checking key files exist and are accessible..."
if [ -f "${BACKEND_DIR}/venv/bin/gunicorn" ]; then
    echo "✅ Gunicorn executable exists"
else
    echo "❌ Gunicorn not found, installing..."
    cd ${BACKEND_DIR}
    sudo -u admin ${BACKEND_DIR}/venv/bin/pip install gunicorn
fi

if [ -f "${BACKEND_DIR}/wsgi.py" ]; then
    echo "✅ WSGI file exists"
else
    echo "❌ WSGI file missing"
    ls -la ${BACKEND_DIR}/*.py 2>/dev/null || echo "No Python files found"
fi

echo -e "\n${BLUE}4. Test Prerequisites${NC}"
echo "===================="

echo "Testing admin user can access files..."
if sudo -u admin test -r ${BACKEND_DIR}/wsgi.py; then
    echo "✅ Admin user can read WSGI file"
else
    echo "❌ Admin user cannot read WSGI file"
fi

if sudo -u admin test -x ${BACKEND_DIR}/venv/bin/gunicorn; then
    echo "✅ Admin user can execute gunicorn"
else
    echo "❌ Admin user cannot execute gunicorn"
fi

echo -e "\nTesting Python imports..."
sudo -u admin bash -c "
cd ${BACKEND_DIR}
export FLASK_APP=wsgi.py
export FLASK_ENV=production
${BACKEND_DIR}/venv/bin/python -c '
try:
    import wsgi
    print(\"✅ WSGI import successful\")
except Exception as e:
    print(f\"❌ WSGI import failed: {e}\")
'
"

echo -e "\n${BLUE}5. Reload and Start Service${NC}"
echo "==========================="

echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "Enabling service..."
sudo systemctl enable ${SERVICE_NAME}

echo "Starting service..."
if sudo systemctl start ${SERVICE_NAME}; then
    echo "✅ Service start command succeeded"
else
    echo "❌ Service start command failed"
fi

echo -e "\n${BLUE}6. Check Service Status${NC}"
echo "======================="

sleep 3

echo "Current service status:"
sudo systemctl status ${SERVICE_NAME} --no-pager -l || true

echo -e "\nRecent logs:"
sudo journalctl -u ${SERVICE_NAME} --no-pager -n 15 || true

echo -e "\n${BLUE}7. Test Connection${NC}"
echo "=================="

echo "Waiting for service to fully start..."
sleep 5

echo "Testing connection to port 5000..."
if curl -s --connect-timeout 10 http://localhost:5000/health >/dev/null 2>&1; then
    RESPONSE=$(curl -s http://localhost:5000/health)
    echo "✅ Service is responding: $RESPONSE"
else
    echo "❌ Service not responding on port 5000"
    
    echo -e "\nChecking what's listening on port 5000:"
    sudo netstat -tulpn | grep :5000 || echo "Nothing listening on port 5000"
    
    echo -e "\nChecking if gunicorn processes are running:"
    pgrep -f gunicorn | xargs -r ps -f || echo "No gunicorn processes found"
fi

echo -e "\n${BLUE}8. Alternative: Manual Test Start${NC}"
echo "================================="

if ! curl -s --connect-timeout 5 http://localhost:5000/health >/dev/null 2>&1; then
    echo "Service isn't working, testing manual startup..."
    
    echo "Stopping service..."
    sudo systemctl stop ${SERVICE_NAME} 2>/dev/null || true
    
    echo "Starting manually as admin user..."
    echo "Command: cd ${BACKEND_DIR} && ${BACKEND_DIR}/venv/bin/gunicorn --bind 127.0.0.1:5000 --workers 1 wsgi:application"
    
    # Start manual test in background
    sudo -u admin bash -c "
    cd ${BACKEND_DIR}
    export FLASK_APP=wsgi.py
    export FLASK_ENV=production
    timeout 15s ${BACKEND_DIR}/venv/bin/gunicorn --bind 127.0.0.1:5000 --workers 1 --timeout 30 wsgi:application
    " &
    
    MANUAL_PID=$!
    sleep 5
    
    if curl -s --connect-timeout 5 http://localhost:5000/health >/dev/null 2>&1; then
        echo "✅ Manual startup works! The issue is with systemd configuration."
        RESPONSE=$(curl -s http://localhost:5000/health)
        echo "Manual response: $RESPONSE"
        
        echo -e "\nThe app works manually, so let's try a different systemd approach..."
        
        # Kill manual process
        kill $MANUAL_PID 2>/dev/null || true
        wait $MANUAL_PID 2>/dev/null || true
        
        # Create even simpler service
        sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=AssisText Flask Backend
After=network.target

[Service]
Type=exec
User=admin
WorkingDirectory=${BACKEND_DIR}
ExecStart=/bin/bash -c 'cd ${BACKEND_DIR} && source venv/bin/activate && gunicorn --bind 127.0.0.1:5000 wsgi:application'
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        
        sudo systemctl daemon-reload
        sudo systemctl start ${SERVICE_NAME}
        sleep 3
        
        if curl -s --connect-timeout 5 http://localhost:5000/health >/dev/null 2>&1; then
            echo "✅ Alternative service file works!"
        else
            echo "❌ Alternative service file also failed"
        fi
        
    else
        echo "❌ Manual startup also failed"
        kill $MANUAL_PID 2>/dev/null || true
        wait $MANUAL_PID 2>/dev/null || true
    fi
fi

echo -e "\n${GREEN}🎉 Namespace Error Fix Attempt Complete${NC}"
echo "========================================"

if curl -s --connect-timeout 5 http://localhost:5000/health >/dev/null 2>&1; then
    echo "✅ SUCCESS: Flask backend is now running!"
    echo "Backend URL: http://localhost:5000"
    echo "Health check: $(curl -s http://localhost:5000/health)"
else
    echo "❌ Service still not working. Additional steps needed:"
    echo ""
    echo "1. Check detailed logs:"
    echo "   sudo journalctl -u ${SERVICE_NAME} -f"
    echo ""
    echo "2. Try running in screen session:"
    echo "   screen -S flask"
    echo "   cd ${BACKEND_DIR}"
    echo "   source venv/bin/activate"
    echo "   gunicorn --bind 127.0.0.1:5000 wsgi:application"
    echo ""
    echo "3. Check if dependencies are missing:"
    echo "   cd ${BACKEND_DIR}"
    echo "   source venv/bin/activate"
    echo "   pip install -r requirements.txt"
fi

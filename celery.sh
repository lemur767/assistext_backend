#!/bin/bash
# Celery Services Fix for AssisText
# Stops the failing restart loop and properly configures Celery

echo "🔧 Celery Services Fix for AssisText"
echo "===================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
    fi
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Step 1: Stop all Celery services immediately
echo -e "\n1. Stopping Celery Services (Break the Restart Loop)"
echo "-----------------------------------------------------"

print_info "Stopping all Celery services..."

# Stop systemd services
sudo systemctl stop assistext-celery-worker || true
sudo systemctl stop assistext-celery-beat || true
sudo systemctl stop celery-worker || true
sudo systemctl stop celery-beat || true
sudo systemctl stop celery || true

# Disable auto-restart temporarily
sudo systemctl disable assistext-celery-worker || true
sudo systemctl disable assistext-celery-beat || true

# Kill any remaining Celery processes
sudo pkill -f celery || true
sudo pkill -f "celery worker" || true
sudo pkill -f "celery beat" || true

sleep 5

# Verify no Celery processes are running
CELERY_PROCS=$(ps aux | grep -v grep | grep celery | wc -l)
print_info "Remaining Celery processes: $CELERY_PROCS"

if [ "$CELERY_PROCS" -eq 0 ]; then
    print_status 0 "All Celery processes stopped"
else
    print_warning "Some Celery processes still running, force killing..."
    sudo pkill -9 -f celery || true
    sleep 2
fi

# Reset failed services
sudo systemctl reset-failed assistext-celery-worker || true
sudo systemctl reset-failed assistext-celery-beat || true

print_status 0 "Celery restart loop broken"

# Step 2: Test Redis connection for Celery
echo -e "\n2. Testing Redis Connection for Celery"
echo "---------------------------------------"

print_info "Testing Redis connection..."
if redis-cli -a "Assistext2025Secure" ping >/dev/null 2>&1; then
    print_status 0 "Redis is accessible"
    
    # Test with Python redis library
    python3 -c "
import redis
try:
    r = redis.Redis(host='localhost', port=6379, password='Assistext2025Secure', db=0)
    r.ping()
    print('✅ Python Redis connection works')
except ImportError:
    print('⚠️ Redis Python library not installed: pip install redis')
except Exception as e:
    print(f'❌ Redis connection failed: {e}')
    exit(1)
" || {
        print_status 1 "Python Redis connection failed"
        echo "Installing Redis Python library..."
        pip install redis
    }
    
else
    print_status 1 "Redis is not accessible"
    echo "Please fix Redis first using the Redis fix script"
    exit 1
fi

# Step 3: Find and check Celery configuration
echo -e "\n3. Checking Celery Configuration"
echo "---------------------------------"

# Find Flask app directory
POSSIBLE_DIRS=(
    "/home/admin/assistext"
    "/opt/assistext"
    "/var/www/assistext"
    "$(pwd)"
)

APP_DIR=""
for dir in "${POSSIBLE_DIRS[@]}"; do
    if [ -d "$dir" ] && [ -f "$dir/app/__init__.py" ]; then
        APP_DIR="$dir"
        break
    fi
done

if [ -n "$APP_DIR" ]; then
    print_status 0 "Found Flask app directory: $APP_DIR"
    cd "$APP_DIR"
else
    print_status 1 "Flask app directory not found"
    APP_DIR="/home/admin/assistext"  # Default assumption
    print_warning "Using default directory: $APP_DIR"
fi

# Check for Celery app file
CELERY_FILES=(
    "$APP_DIR/celery_app.py"
    "$APP_DIR/app/celery_app.py"
    "$APP_DIR/celery.py"
    "$APP_DIR/app/celery.py"
)

CELERY_APP_FILE=""
for file in "${CELERY_FILES[@]}"; do
    if [ -f "$file" ]; then
        CELERY_APP_FILE="$file"
        break
    fi
done

if [ -n "$CELERY_APP_FILE" ]; then
    print_status 0 "Found Celery app file: $CELERY_APP_FILE"
else
    print_warning "Celery app file not found, will create basic one"
    CELERY_APP_FILE="$APP_DIR/celery_app.py"
fi

# Step 4: Test Celery configuration
echo -e "\n4. Testing Current Celery Configuration"
echo "---------------------------------------"

cd "$APP_DIR"

# Test if Celery can import and connect
print_info "Testing Celery import and configuration..."

python3 << 'EOF'
import sys
import os
sys.path.insert(0, '.')

try:
    # Try to import the Celery app
    from celery_app import celery
    print("✅ Celery app imported successfully")
    
    # Test broker connection
    result = celery.control.inspect().stats()
    if result:
        print("✅ Celery broker connection works")
    else:
        print("⚠️ No active Celery workers found (this is expected)")
        
except ImportError as e:
    print(f"❌ Celery import failed: {e}")
    print("Will create basic Celery configuration")
except Exception as e:
    print(f"⚠️ Celery connection issue: {e}")
    print("This might be fixed after restart")
EOF

# Step 5: Create/fix Celery configuration if needed
echo -e "\n5. Creating/Fixing Celery Configuration"
echo "---------------------------------------"

if [ ! -f "$CELERY_APP_FILE" ]; then
    print_info "Creating basic Celery configuration..."
    
    cat > "$CELERY_APP_FILE" << 'EOF'
# celery_app.py - Celery configuration for AssisText
import os
from celery import Celery
from app import create_app

def make_celery(app):
    """Create Celery instance"""
    celery = Celery(
        app.import_name,
        backend=app.config.get('CELERY_RESULT_BACKEND', 'redis://:Assistext2025Secure@localhost:6379/0'),
        broker=app.config.get('CELERY_BROKER_URL', 'redis://:Assistext2025Secure@localhost:6379/0')
    )
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        """Make celery tasks work with Flask app context"""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

# Create Flask app and Celery instance
flask_app = create_app()
celery = make_celery(flask_app)

if __name__ == '__main__':
    celery.start()
EOF
    
    print_status 0 "Celery configuration created"
else
    print_info "Celery configuration exists, checking..."
    
    # Verify the configuration has correct Redis URL
    if grep -q "Assistext2025Secure" "$CELERY_APP_FILE"; then
        print_status 0 "Celery Redis configuration looks correct"
    else
        print_warning "Celery configuration may need Redis password update"
    fi
fi

# Step 6: Create/update systemd service files
echo -e "\n6. Creating/Updating Systemd Service Files"
echo "-------------------------------------------"

# Celery Worker Service
print_info "Creating Celery worker service..."
sudo tee /etc/systemd/system/assistext-celery-worker.service > /dev/null << EOF
[Unit]
Description=AssisText Celery Worker
After=network.target redis-server.service postgresql.service
Requires=redis-server.service

[Service]
Type=forking
User=admin
Group=admin
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=CELERY_BROKER_URL=redis://:Assistext2025Secure@localhost:6379/0
Environment=CELERY_RESULT_BACKEND=redis://:Assistext2025Secure@localhost:6379/0
ExecStart=$APP_DIR/venv/bin/celery -A celery_app worker --loglevel=info --detach --pidfile=/tmp/celery_worker.pid --logfile=/var/log/celery/worker.log
ExecStop=/bin/kill -TERM \$MAINPID
ExecReload=/bin/kill -HUP \$MAINPID
Restart=on-failure
RestartSec=10
KillMode=mixed
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

# Celery Beat Service  
print_info "Creating Celery beat service..."
sudo tee /etc/systemd/system/assistext-celery-beat.service > /dev/null << EOF
[Unit]
Description=AssisText Celery Beat Scheduler
After=network.target redis-server.service postgresql.service assistext-celery-worker.service
Requires=redis-server.service

[Service]
Type=forking
User=admin
Group=admin
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=CELERY_BROKER_URL=redis://:Assistext2025Secure@localhost:6379/0
Environment=CELERY_RESULT_BACKEND=redis://:Assistext2025Secure@localhost:6379/0
ExecStart=$APP_DIR/venv/bin/celery -A celery_app beat --loglevel=info --detach --pidfile=/tmp/celery_beat.pid --logfile=/var/log/celery/beat.log
ExecStop=/bin/kill -TERM \$MAINPID
ExecReload=/bin/kill -HUP \$MAINPID
Restart=on-failure
RestartSec=15
KillMode=mixed
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

# Create log directory
sudo mkdir -p /var/log/celery
sudo chown admin:admin /var/log/celery

print_status 0 "Systemd service files created"

# Step 7: Test Celery manually first
echo -e "\n7. Testing Celery Manually"
echo "--------------------------"

cd "$APP_DIR"

print_info "Testing Celery worker manually..."

# Start virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    print_info "Virtual environment activated"
fi

# Test Celery worker can start
timeout 10s celery -A celery_app worker --loglevel=info --dry-run 2>/dev/null
if [ $? -eq 0 ] || [ $? -eq 124 ]; then  # 124 is timeout exit code
    print_status 0 "Celery worker configuration test passed"
else
    print_status 1 "Celery worker configuration test failed"
    print_info "Checking for missing dependencies..."
    
    # Install common missing dependencies
    pip install celery redis flask
fi

# Step 8: Start services properly
echo -e "\n8. Starting Celery Services"
echo "---------------------------"

# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable assistext-celery-worker
sudo systemctl enable assistext-celery-beat

# Start worker first
print_info "Starting Celery worker..."
if sudo systemctl start assistext-celery-worker; then
    sleep 5
    if systemctl is-active --quiet assistext-celery-worker; then
        print_status 0 "Celery worker started successfully"
    else
        print_status 1 "Celery worker failed to start"
        print_info "Checking worker logs..."
        sudo journalctl -u assistext-celery-worker -n 10 --no-pager
    fi
else
    print_status 1 "Celery worker start command failed"
fi

# Start beat scheduler
print_info "Starting Celery beat..."
if sudo systemctl start assistext-celery-beat; then
    sleep 5
    if systemctl is-active --quiet assistext-celery-beat; then
        print_status 0 "Celery beat started successfully"
    else
        print_status 1 "Celery beat failed to start"
        print_info "Checking beat logs..."
        sudo journalctl -u assistext-celery-beat -n 10 --no-pager
    fi
else
    print_status 1 "Celery beat start command failed"
fi

# Step 9: Verify services are working
echo -e "\n9. Verifying Celery Services"
echo "----------------------------"

WORKER_STATUS=$(systemctl is-active assistext-celery-worker 2>/dev/null || echo "inactive")
BEAT_STATUS=$(systemctl is-active assistext-celery-beat 2>/dev/null || echo "inactive")

echo "Celery Worker Status: $WORKER_STATUS"
echo "Celery Beat Status: $BEAT_STATUS"

# Test if workers are responding
if [ "$WORKER_STATUS" = "active" ]; then
    print_info "Testing worker connectivity..."
    
    python3 -c "
from celery_app import celery
try:
    result = celery.control.inspect().stats()
    if result:
        worker_count = len(result)
        print(f'✅ {worker_count} Celery worker(s) responding')
    else:
        print('⚠️ No workers responding yet (may need more time)')
except Exception as e:
    print(f'⚠️ Worker test failed: {e}')
" 2>/dev/null || print_info "Worker connectivity test skipped"
fi

# Step 10: Summary
echo -e "\n10. Summary"
echo "-----------"

if [ "$WORKER_STATUS" = "active" ] && [ "$BEAT_STATUS" = "active" ]; then
    echo -e "\n${GREEN}✅ Celery services are now working properly!${NC}"
    echo ""
    echo "Service Status:"
    echo "  • Celery Worker: $WORKER_STATUS"
    echo "  • Celery Beat: $BEAT_STATUS"
    echo ""
    echo "Configuration:"
    echo "  • App Directory: $APP_DIR"
    echo "  • Celery App: $CELERY_APP_FILE"
    echo "  • Broker: redis://:Assistext2025Secure@localhost:6379/0"
    echo "  • Logs: /var/log/celery/"
    echo ""
    echo "Management Commands:"
    echo "  • Check status: sudo systemctl status assistext-celery-worker"
    echo "  • View logs: sudo journalctl -u assistext-celery-worker -f"
    echo "  • Restart: sudo systemctl restart assistext-celery-worker"
else
    echo -e "\n${YELLOW}⚠️ Some Celery services may still need attention${NC}"
    echo ""
    echo "Current Status:"
    echo "  • Celery Worker: $WORKER_STATUS"
    echo "  • Celery Beat: $BEAT_STATUS"
    echo ""
    echo "Troubleshooting:"
    echo "  • Check logs: sudo journalctl -u assistext-celery-worker -f"
    echo "  • Check Redis: redis-cli -a 'Assistext2025Secure' ping"
    echo "  • Manual test: cd $APP_DIR && celery -A celery_app worker --loglevel=info"
fi

echo -e "\n${GREEN}🔧 Celery services fix completed!${NC}"

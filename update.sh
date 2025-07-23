#!/bin/bash
# Update AssisText Celery Services for Email Tasks
# Working Directory: /opt/assistext_backend

echo "🔧 Updating Celery Services for Email Tasks"
echo "Directory: /opt/assistext_backend"
echo "==========================================="

# Stop existing services
echo "1. Stopping existing Celery services..."
sudo systemctl stop assistext-celery-worker
sudo systemctl stop assistext-celery-beat

# Update Celery Worker Service with Email Queue
echo "2. Updating Celery worker service..."
sudo tee /etc/systemd/system/assistext-celery-worker.service > /dev/null << 'EOF'
[Unit]
Description=AssisText Celery Worker
After=network.target redis-server.service postgresql.service
Requires=redis-server.service

[Service]
Type=forking
User=admin
Group=admin
WorkingDirectory=/opt/assistext_backend
Environment=PATH=/opt/assistext_backend/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=CELERY_BROKER_URL=redis://:Assistext2025Secure@localhost:6379/0
Environment=CELERY_RESULT_BACKEND=redis://:Assistext2025Secure@localhost:6379/0
ExecStart=/opt/assistext_backend/venv/bin/celery -A celery_app worker --loglevel=info --queues=default,email_notifications,trial_management --detach --pidfile=/tmp/celery_worker.pid --logfile=/var/log/celery/worker.log
ExecStop=/bin/kill -TERM $MAINPID
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=10
KillMode=mixed
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

# Create separate worker for email notifications (optional - for high volume)
echo "3. Creating dedicated email worker service..."
sudo tee /etc/systemd/system/assistext-celery-email-worker.service > /dev/null << 'EOF'
[Unit]
Description=AssisText Celery Email Worker
After=network.target redis-server.service postgresql.service
Requires=redis-server.service

[Service]
Type=forking
User=admin
Group=admin
WorkingDirectory=/opt/assistext_backend
Environment=PATH=/opt/assistext_backend/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=CELERY_BROKER_URL=redis://:Assistext2025Secure@localhost:6379/0
Environment=CELERY_RESULT_BACKEND=redis://:Assistext2025Secure@localhost:6379/0
ExecStart=/opt/assistext_backend/venv/bin/celery -A celery_app worker --loglevel=info --queues=email_notifications --concurrency=2 --detach --pidfile=/tmp/celery_email_worker.pid --logfile=/var/log/celery/email_worker.log
ExecStop=/bin/kill -TERM $MAINPID
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=10
KillMode=mixed
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

# Keep existing beat service (no changes needed)
echo "4. Celery beat service remains unchanged..."

# Create email-specific log files
sudo mkdir -p /var/log/celery
sudo touch /var/log/celery/email_worker.log
sudo chown admin:admin /var/log/celery/email_worker.log

# Reload systemd and start services
echo "5. Reloading systemd and starting services..."
sudo systemctl daemon-reload

# Enable all services 
sudo systemctl enable assistext-celery-worker
sudo systemctl enable assistext-celery-beat
sudo systemctl enable assistext-celery-email-worker

# Start services
echo "6. Starting Celery services..."
sudo systemctl start assistext-celery-worker
sleep 3
sudo systemctl start assistext-celery-email-worker  
sleep 3
sudo systemctl start assistext-celery-beat

# Check status
echo "7. Checking service status..."
echo "Main Worker Status: $(systemctl is-active assistext-celery-worker)"
echo "Email Worker Status: $(systemctl is-active assistext-celery-email-worker)"
echo "Beat Scheduler Status: $(systemctl is-active assistext-celery-beat)"

echo ""
echo "✅ Celery services updated for email tasks!"
echo ""
echo "📊 Management Commands:"
echo "  • Check main worker: sudo systemctl status assistext-celery-worker"
echo "  • Check email worker: sudo systemctl status assistext-celery-email-worker"
echo "  • View main worker logs: sudo journalctl -u assistext-celery-worker -f"
echo "  • View email worker logs: sudo journalctl -u assistext-celery-email-worker -f"
echo "  • View beat logs: sudo journalctl -u assistext-celery-beat -f"
echo ""
echo "🔄 To restart all services:"
echo "  sudo systemctl restart assistext-celery-worker assistext-celery-email-worker assistext-celery-beat"
echo ""
echo "📁 Working Directory: /opt/assistext_backend"

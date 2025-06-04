import multiprocessing
import os

# Server socket
bind = "127.0.0.1:5000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "eventlet"  # For SocketIO support
worker_connections = 1000
timeout = 120
keepalive = 5

# Restart workers after this many requests to prevent memory leaks
max_requests = 1000
max_requests_jitter = 100

# User and group
user = "smsapp"
group = "smsapp"

# Logging
errorlog = "/var/log/gunicorn-error.log"
accesslog = "/var/log/gunicorn-access.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "sms-ai-responder"

# Server mechanics
daemon = False
pidfile = "/var/run/gunicorn/sms-ai-responder.pid"
tmp_upload_dir = None

# SSL (if needed)
# keyfile = "/path/to/ssl/key.pem"
# certfile = "/path/to/ssl/cert.pem"

# Preload application for better performance
preload_app = True

# Worker process lifecycle
def on_starting(server):
    server.log.info("SMS AI Responder starting...")

def when_ready(server):
    server.log.info("SMS AI Responder ready to serve requests")

def on_exit(server):
    server.log.info("SMS AI Responder shutting down...")
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
user = "admin"
group = "admin"

# Logging
errorlog = "/var/log/gunicorn-error.log"
accesslog = "/var/log/gunicorn-access.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "assistext_backend"

# Server mechanics
daemon = False
pidfile = "/var/run/gunicorn/assistext_backend.pid"
tmp_upload_dir = None

# SSL (if needed)
keyfile = "/etc/letsencrypt/live/backend.assitext.ca/fullchain.pem";
certfile = "/etc/letsencrypt/live/backend.assitext.ca/cert.pem";

# Preload application for better performance
preload_app = True

# Worker process lifecycle
def on_starting(server):
    server.log.info("Backend Starting........")

def when_ready(server):
    server.log.info("Backend Running")

def on_exit(server):
    server.log.info("Shutdown.....")

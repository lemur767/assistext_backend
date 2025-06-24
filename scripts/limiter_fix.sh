#!/bin/bash

# Quick fix for Flask-Limiter configuration issue
cd /opt/assistext_backend

# Backup the current file
cp app/__init__.py app/__init__.py.backup

# Find the problematic Limiter configuration and fix it
python3 << 'EOF'
import re

print("Fixing Flask-Limiter configuration...")

# Read the current file
with open('app/__init__.py', 'r') as f:
    content = f.read()

# Pattern to find the Limiter initialization
limiter_pattern = r'limiter = Limiter\([^)]*\)'

# Working Limiter configuration
working_limiter = '''limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["200 per day", "50 per hour"],
        storage_uri=app.config.get('REDIS_URL', 'memory://')
    )'''

# Replace the problematic Limiter configuration
if re.search(limiter_pattern, content):
    content = re.sub(limiter_pattern, working_limiter, content, flags=re.DOTALL)
    
    # Write the fixed content back
    with open('app/__init__.py', 'w') as f:
        f.write(content)
    
    print("Flask-Limiter configuration fixed!")
    print("You can now run the setup script again.")
else:
    print("No Limiter configuration found to fix.")
    print("Please check your app/__init__.py file manually.")
EOF

# Alternative: If you want to temporarily disable rate limiting, uncomment this:
# sed -i 's/limiter = Limiter(/# limiter = Limiter(/g' app/__init__.py
# sed -i 's/register_auth_routes(api, limiter)/register_auth_routes(api)/g' app/__init__.py

echo "Fix applied. Try running the setup script again."

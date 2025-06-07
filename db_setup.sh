#!/bin/bash

echo "=== PostgreSQL Setup for SMS AI Responder ==="

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "Installing PostgreSQL..."
    sudo apt update
    sudo apt install postgresql postgresql-contrib postgresql-client -y
fi

# Start PostgreSQL service
echo "Starting PostgreSQL service..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Check PostgreSQL status
echo "PostgreSQL status:"
sudo systemctl status postgresql --no-pager

echo ""
echo "=== Creating Database and User ==="

# Switch to postgres user and create database/user
sudo -u postgres psql << 'EOF'
-- Create application user
CREATE USER app_user WITH PASSWORD 'AssisText2025!SecureDB';

-- Create databases
CREATE DATABASE assistext_prod OWNER app_user;
CREATE DATABASE assistext_dev OWNER app_user;
CREATE DATABASE assistext_test OWNER app_user;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE assistext_prod TO app_user;
GRANT ALL PRIVILEGES ON DATABASE assistext_dev TO app_user;
GRANT ALL PRIVILEGES ON DATABASE assistext_test TO app_user;

-- Grant schema privileges
\c assistext_dev
GRANT ALL ON SCHEMA public TO app_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO app_user;

\c assistext_prod
GRANT ALL ON SCHEMA public TO app_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO app_user;

\c assistext_test
GRANT ALL ON SCHEMA public TO app_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO app_user;

-- List databases to verify
\l

-- Exit
\q
EOF

echo ""
echo "=== Configuring PostgreSQL for Local Connections ==="

# Find PostgreSQL version and config location
PG_VERSION=15
echo "PostgreSQL version: $PG_VERSION"

# Common config paths
if [ -f "/etc/postgresql/$PG_VERSION/main/pg_hba.conf" ]; then
    PG_HBA_CONF="/etc/postgresql/$PG_VERSION/main/pg_hba.conf"
    PG_CONF="/etc/postgresql/$PG_VERSION/main/postgresql.conf"
elif [ -f "/var/lib/pgsql/data/pg_hba.conf" ]; then
    PG_HBA_CONF="/var/lib/pgsql/data/pg_hba.conf"
    PG_CONF="/var/lib/pgsql/data/postgresql.conf"
else
    echo "Could not find PostgreSQL config files. Please configure manually."
    exit 1
fi

echo "Using config file: $PG_HBA_CONF"

# Backup original config
sudo cp "$PG_HBA_CONF" "$PG_HBA_CONF.backup"

# Configure pg_hba.conf for local connections
echo "Configuring pg_hba.conf..."
sudo tee "$PG_HBA_CONF" > /dev/null << 'EOF'
# PostgreSQL Client Authentication Configuration File
# TYPE  DATABASE        USER            ADDRESS                 METHOD

# "local" is for Unix domain socket connections only
local   all             postgres                                peer
local   all             all                                     md5

# IPv4 local connections:
host    all             postgres        127.0.0.1/32            md5
host    all             app_user        127.0.0.1/32            md5
host    all             all             127.0.0.1/32            md5

# IPv6 local connections:
host    all             postgres        ::1/128                 md5
host    all             app_user        ::1/128                 md5
host    all             all             ::1/128                 md5

# Allow connections from localhost
host    all             all             localhost               md5

# Deny all other connections
host    all             all             0.0.0.0/0               reject
EOF

# Configure postgresql.conf
echo "Configuring postgresql.conf..."
sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = 'localhost'/" "$PG_CONF"
sudo sed -i "s/#port = 5432/port = 5432/" "$PG_CONF"

# Restart PostgreSQL to apply changes
echo "Restarting PostgreSQL..."
sudo systemctl restart postgresql

# Wait a moment for service to restart
sleep 3

echo ""
echo "=== Testing Database Connection ==="

# Test connection
export PGPASSWORD='secure_password_123'
if psql -h localhost -U app_user -d assistext_dev -c "SELECT version();" > /dev/null 2>&1; then
    echo "✅ Database connection successful!"
else
    echo "❌ Database connection failed. Checking status..."
    sudo systemctl status postgresql --no-pager
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Database credentials:"
echo "  Host: localhost"
echo "  Port: 5432"
echo "  User: app_user"
echo "  Password: secure_password_123"
echo "  Databases: assistext_dev, assistext_prod, assistext_test"
echo ""
echo "Connection URLs:"
echo "  Development: postgresql://app_user:secure_password_123@localhost/assistext_dev"
echo "  Production:  postgresql://app_user:secure_password_123@localhost/assistext_prod"
echo "  Testing:     postgresql://app_user:secure_password_123@localhost/assistext_test"

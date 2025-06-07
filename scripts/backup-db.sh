#!/bin/bash
set -e

BACKUP_DIR="/opt/backups"
DATE=$(date +"%Y%m%d_%H%M%S")
DB_NAME="assistext_prod"
DB_USER="app_user"
RETENTION_DAYS=7

# Create backup directory
mkdir -p $BACKUP_DIR

# Set PGPASSWORD for automated backup
export PGPASSWORD='AssisText2025!SecureDB'

# Create full database backup with compression
pg_dump -h localhost -U $DB_USER -d $DB_NAME -F c -v --no-owner --no-privileges > $BACKUP_DIR/backup_$DATE.dump

# Create schema-only backup
pg_dump -h localhost -U $DB_USER -d $DB_NAME -s > $BACKUP_DIR/schema_$DATE.sql

# Verify backup integrity
pg_restore --list $BACKUP_DIR/backup_$DATE.dump > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "$(date): Backup successful - backup_$DATE.dump" >> $BACKUP_DIR/backup.log
else
    echo "$(date): Backup verification failed - backup_$DATE.dump" >> $BACKUP_DIR/backup.log
    exit 1
fi

# Clean old backups
find $BACKUP_DIR -name "backup_*.dump" -mtime +$RETENTION_DAYS -delete
find $BACKUP_DIR -name "schema_*.sql" -mtime +$RETENTION_DAYS -delete

echo "$(date): Backup completed and old backups cleaned" >> $BACKUP_DIR/backup.log

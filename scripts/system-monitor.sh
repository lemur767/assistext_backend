#!/bin/bash
LOG_FILE="/var/log/assistext-monitor.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$DATE] Backend Server Status Check" >> $LOG_FILE

# Check CPU, Memory, Disk
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}')
MEM_USAGE=$(free | grep Mem | awk '{printf("%.1f"), $3/$2 * 100.0}')
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')

echo "[$DATE] CPU: $CPU_USAGE%, Memory: $MEM_USAGE%, Disk: $DISK_USAGE%" >> $LOG_FILE

# Check services
systemctl is-active nginx >> $LOG_FILE 2>&1
systemctl is-active postgresql >> $LOG_FILE 2>&1
systemctl is-active redis-server >> $LOG_FILE 2>&1
supervisorctl status >> $LOG_FILE 2>&1

# Check database connectivity
export PGPASSWORD='AssisText2025!SecureDB'
pg_isready -h localhost -p 5432 -U app_user -d assistext_prod >> $LOG_FILE 2>&1

# Check Redis connectivity
redis-cli -a 'AssisText2025!Redis' ping >> $LOG_FILE 2>&1

echo "[$DATE] ------------------------" >> $LOG_FILE

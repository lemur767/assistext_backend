#!/bin/bash
LOG_FILE="/var/log/assistext-security-monitor.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$DATE] Security Monitor Check" >> $LOG_FILE

# Check for failed login attempts
FAILED_LOGINS=$(grep "Failed password" /var/log/auth.log | grep "$(date '+%b %d')" | wc -l)
if [ $FAILED_LOGINS -gt 10 ]; then
    echo "[$DATE] ALERT: High number of failed login attempts: $FAILED_LOGINS" >> $LOG_FILE
fi

# Check for nginx errors
NGINX_ERRORS=$(grep "error" /var/log/nginx/error.log | grep "$(date '+%Y/%m/%d')" | wc -l)
if [ $NGINX_ERRORS -gt 50 ]; then
    echo "[$DATE] ALERT: High number of nginx errors: $NGINX_ERRORS" >> $LOG_FILE
fi

# Check fail2ban status
BANNED_IPS=$(fail2ban-client status | grep "Jail list" | awk -F: '{print $2}' | xargs -n1 fail2ban-client status | grep "Currently banned" | wc -l)
if [ $BANNED_IPS -gt 0 ]; then
    echo "[$DATE] INFO: Currently banned IPs: $BANNED_IPS" >> $LOG_FILE
fi

# Check SSL certificate expiry
if [ -f "/etc/letsencrypt/live/*/cert.pem" ]; then
    CERT_FILE=$(find /etc/letsencrypt/live/*/cert.pem | head -1)
    EXPIRY_DATE=$(openssl x509 -enddate -noout -in $CERT_FILE | cut -d= -f2)
    EXPIRY_EPOCH=$(date -d "$EXPIRY_DATE" +%s)
    CURRENT_EPOCH=$(date +%s)
    DAYS_UNTIL_EXPIRY=$(( (EXPIRY_EPOCH - CURRENT_EPOCH) / 86400 ))
    
    if [ $DAYS_UNTIL_EXPIRY -lt 30 ]; then
        echo "[$DATE] ALERT: SSL certificate expires in $DAYS_UNTIL_EXPIRY days" >> $LOG_FILE
    fi
fi

echo "[$DATE] Security check completed" >> $LOG_FILE

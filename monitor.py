#!/usr/bin/env python3
import psutil
import requests
import json
from datetime import datetime

def check_system_health():
    """Check system health and log metrics"""
    metrics = {
        'timestamp': datetime.now().isoformat(),
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent,
        'backend_status': 'unknown'
    }
    
    # Check backend health
    try:
        response = requests.get('http://localhost:8000/health', timeout=5)
        if response.status_code == 200:
            metrics['backend_status'] = 'healthy'
        else:
            metrics['backend_status'] = 'unhealthy'
    except:
        metrics['backend_status'] = 'down'
    
    # Log metrics
    with open('/var/log/assistext/system-metrics.log', 'a') as f:
        f.write(json.dumps(metrics) + '\n')
    
    print(f"System Health: CPU {metrics['cpu_percent']}% | Memory {metrics['memory_percent']}% | Disk {metrics['disk_percent']}% | Backend {metrics['backend_status']}")

if __name__ == '__main__':
    check_system_health()

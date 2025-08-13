import logging
import logging.config
import os
from datetime import datetime

def setup_logging(app):
    """Configure application logging"""
    
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    log_file = os.getenv('LOG_FILE', '/var/log/assistext/app.log')
    
    # Ensure log directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'detailed': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s [%(filename)s:%(lineno)d]'
            },
            'simple': {
                'format': '%(asctime)s [%(levelname)s] %(message)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'INFO',
                'formatter': 'simple',
                'stream': 'ext://sys.stdout'
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': log_level,
                'formatter': 'detailed',
                'filename': log_file,
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5
            }
        },
        'loggers': {
            'app': {
                'level': log_level,
                'handlers': ['console', 'file'],
                'propagate': False
            },
            'signalwire': {
                'level': 'INFO',
                'handlers': ['file'],
                'propagate': False
            },
            'stripe': {
                'level': 'INFO',
                'handlers': ['file'],
                'propagate': False
            }
        },
        'root': {
            'level': 'WARNING',
            'handlers': ['console', 'file']
        }
    }
    
    logging.config.dictConfig(logging_config)
    
    # Set Flask app logger
    app.logger.setLevel(getattr(logging, log_level))
    
    # Log startup
    app.logger.info(f"AssisText backend started - Log level: {log_level}")

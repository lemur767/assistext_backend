#!/usr/bin/env python3
"""
Celery Worker Entry Point
celery_app.py - Start Celery workers for background processing
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add app to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and configure Celery
from app.extensions import make_celery

# Create Celery app
celery_app = make_celery()

if __name__ == '__main__':
    celery_app.start()
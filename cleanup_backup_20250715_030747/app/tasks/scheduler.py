# app/tasks/scheduler.py
from flask import current_app
from app.tasks.billing import update_all_usage_tracking, process_monthly_billing
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

def init_scheduler(app):
    """Initialize the task scheduler"""
    scheduler = BackgroundScheduler()
    
    # Update usage tracking every 6 hours
    scheduler.add_job(
        update_all_usage_tracking,
        trigger=CronTrigger(hour='*/6'),
        id='update_usage_tracking',
        name='Update Twilio usage tracking for all users',
        max_instances=1,
        replace_existing=True
    )
    
    # Process monthly billing on the 1st of each month
    scheduler.add_job(
        process_monthly_billing,
        trigger=CronTrigger(day='1', hour='2'),  # 2 AM on the 1st of each month
        id='process_monthly_billing',
        name='Process monthly billing for all users',
        max_instances=1,
        replace_existing=True
    )
    
    scheduler.start()
    
    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())
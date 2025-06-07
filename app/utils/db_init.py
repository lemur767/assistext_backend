# app/utils/db_init.py
from app.models import SubscriptionPlan, BannedWord
from app.extensions import db
import json


def init_default_data():
    """Initialize database with default data"""
    # Create default subscription plans if they don't exist
    if SubscriptionPlan.query.count() == 0:
        plans = [
            {
                "name": "Free",
                "description": "Basic plan with limited features",
                "price": 0.00,
                "billing_interval": "month",
                "max_profiles": 1,
                "max_ai_responses_per_day": 20,
                "retention_days": 7,
                "features": json.dumps({
                    "ai_responses": True,
                    "auto_replies": True,
                    "business_hours": True,
                    "analytics": False,
                    "api_access": False
                })
            },
            {
                "name": "Basic",
                "description": "Standard plan for individuals",
                "price": 19.99,
                "billing_interval": "month",
                "max_profiles": 2,
                "max_ai_responses_per_day": 100,
                "retention_days": 30,
                "features": json.dumps({
                    "ai_responses": True,
                    "auto_replies": True,
                    "business_hours": True,
                    "analytics": True,
                    "api_access": False
                })
            },
            {
                "name": "Professional",
                "description": "Advanced plan for power users",
                "price": 49.99,
                "billing_interval": "month",
                "max_profiles": 5,
                "max_ai_responses_per_day": 500,
                "retention_days": 90,
                "features": json.dumps({
                    "ai_responses": True,
                    "auto_replies": True,
                    "business_hours": True,
                    "analytics": True,
                    "api_access": True,
                    "priority_support": True
                })
            },
            {
                "name": "Enterprise",
                "description": "Full-featured plan for agencies",
                "price": 99.99,
                "billing_interval": "month",
                "max_profiles": 15,
                "max_ai_responses_per_day": 2000,
                "retention_days": 365,
                "features": json.dumps({
                    "ai_responses": True,
                    "auto_replies": True,
                    "business_hours": True,
                    "analytics": True,
                    "api_access": True,
                    "priority_support": True,
                    "white_label": True,
                    "custom_ai_training": True
                })
            }
        ]
        
        for plan_data in plans:
            plan = SubscriptionPlan(**plan_data)
            db.session.add(plan)
        
        db.session.commit()
        print("Default subscription plans created.")
    
    # Create common banned words if they don't exist
    if BannedWord.query.count() == 0:
        banned_words = [
            {"word": "police", "category": "legal", "severity": 4, "action": "flag"},
            {"word": "cop", "category": "legal", "severity": 4, "action": "flag"},
            {"word": "law enforcement", "category": "legal", "severity": 5, "action": "flag"},
            {"word": "arrest", "category": "legal", "severity": 4, "action": "flag"},
            {"word": "sting", "category": "legal", "severity": 5, "action": "flag"},
            {"word": "setup", "category": "legal", "severity": 4, "action": "flag"},
            {"word": "underage", "category": "legal", "severity": 5, "action": "block"},
            {"word": "minor", "category": "legal", "severity": 5, "action": "block"},
            {"word": "illegal", "category": "legal", "severity": 3, "action": "flag"},
            {"word": "bust", "category": "legal", "severity": 4, "action": "flag"}
        ]
        
        for word_data in banned_words:
            word = BannedWord(**word_data)
            db.session.add(word)
        
        db.session.commit()
        print("Default banned words created.")
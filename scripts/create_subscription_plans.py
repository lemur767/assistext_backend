"""Setup default subscription plans with SignalWire features"""

from app import create_app
from app.extensions import db
from app.models.billing import SubscriptionPlan

def create_subscription_plans():
    """Create default subscription plans optimized for SignalWire"""
    
    plans = [
        {
            'name': 'Free Trial',
            'description': 'Perfect for testing our SMS AI system',
            'price_monthly': 0.00,
            'price_yearly': 0.00,
            'max_profiles': 1,
            'max_ai_responses': 100,
            'max_phone_numbers': 1,
            'message_retention_days': 30,
            'features': {
                'ai_responses': True,
                'business_hours': True,
                'auto_replies': True,
                'basic_analytics': True,
                'canadian_numbers': True,
                'sms_support': True,
                'email_support': False,
                'priority_support': False,
                'custom_integrations': False,
                'advanced_analytics': False
            },
            'is_active': True
        },
        {
            'name': 'Starter',
            'description': 'Great for individual escorts getting started',
            'price_monthly': 29.99,
            'price_yearly': 299.99,
            'max_profiles': 3,
            'max_ai_responses': 2000,
            'max_phone_numbers': 3,
            'message_retention_days': 90,
            'features': {
                'ai_responses': True,
                'business_hours': True,
                'auto_replies': True,
                'basic_analytics': True,
                'canadian_numbers': True,
                'sms_support': True,
                'email_support': True,
                'priority_support': False,
                'custom_integrations': False,
                'advanced_analytics': True,
                'message_templates': True,
                'client_management': True
            },
            'is_active': True
        },
        {
            'name': 'Professional',
            'description': 'Perfect for established professionals',
            'price_monthly': 79.99,
            'price_yearly': 799.99,
            'max_profiles': 10,
            'max_ai_responses': 10000,
            'max_phone_numbers': 10,
            'message_retention_days': 365,
            'features': {
                'ai_responses': True,
                'business_hours': True,
                'auto_replies': True,
                'basic_analytics': True,
                'canadian_numbers': True,
                'sms_support': True,
                'email_support': True,
                'priority_support': True,
                'custom_integrations': True,
                'advanced_analytics': True,
                'message_templates': True,
                'client_management': True,
                'custom_ai_training': True,
                'api_access': True,
                'white_label': False
            },
            'is_active': True
        },
        {
            'name': 'Agency',
            'description': 'For agencies managing multiple profiles',
            'price_monthly': 199.99,
            'price_yearly': 1999.99,
            'max_profiles': 50,
            'max_ai_responses': 50000,
            'max_phone_numbers': 50,
            'message_retention_days': 730,
            'features': {
                'ai_responses': True,
                'business_hours': True,
                'auto_replies': True,
                'basic_analytics': True,
                'canadian_numbers': True,
                'sms_support': True,
                'email_support': True,
                'priority_support': True,
                'custom_integrations': True,
                'advanced_analytics': True,
                'message_templates': True,
                'client_management': True,
                'custom_ai_training': True,
                'api_access': True,
                'white_label': True,
                'team_management': True,
                'dedicated_support': True,
                'custom_onboarding': True
            },
            'is_active': True
        }
    ]
    
    for plan_data in plans:
        # Check if plan already exists
        existing_plan = SubscriptionPlan.query.filter_by(name=plan_data['name']).first()
        if not existing_plan:
            plan = SubscriptionPlan(**plan_data)
            db.session.add(plan)
    
    db.session.commit()
    print("Subscription plans created successfully!")

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        create_subscription_plans()
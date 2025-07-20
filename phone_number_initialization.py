# scripts/initialize_phone_number.py
"""
Initialize the database with your phone number for development/testing
Run this script after database setup to configure your phone number

Usage:
cd /opt/assistext_backend
source venv/bin/activate  
python scripts/initialize_phone_number.py
"""

import os
import sys
from datetime import datetime, timedelta

# Add the parent directory to Python path
backend_path = '/opt/assistext_backend'
sys.path.insert(0, backend_path)

def initialize_phone_number():
    """Initialize your phone number in the system"""
    from app import create_app
    from app.models.user import User
    from app.models.subscription import Subscription, SubscriptionPlan
    from app.models.billing import PaymentMethod
    from app.extensions import db
    
    app = create_app()
    
    with app.app_context():
        print("🔧 Initializing phone number configuration...")
        print(f"📁 Backend path: {backend_path}")
        
        # Your phone number details
        YOUR_PHONE = "+12899171708"
        YOUR_EMAIL = "admin@assitext.ca"  # Change this to your email
        YOUR_USERNAME = "admin"
        
        # Check if admin user exists
        admin_user = User.query.filter_by(email=YOUR_EMAIL).first()
        
        if not admin_user:
            print("👤 Creating admin user...")
            admin_user = User(
                username=YOUR_USERNAME,
                email=YOUR_EMAIL,
                password="admin123"  # Change this!
            )
            admin_user.first_name = "Admin"
            admin_user.last_name = "User"
            admin_user.is_verified = True
            admin_user.is_active = True
            
            db.session.add(admin_user)
            db.session.flush()
        else:
            print("👤 Admin user already exists, updating...")
        
        # Configure SignalWire settings for admin user
        print("📞 Configuring phone number...")
        admin_user.signalwire_phone_number = YOUR_PHONE
        admin_user.signalwire_setup_completed = True
        admin_user.signalwire_subproject_id = "admin_subproject_main"
        admin_user.signalwire_subproject_token = "admin_token_main"
        admin_user.trial_phone_expires_at = datetime.utcnow() + timedelta(days=365)  # 1 year
        admin_user.ai_enabled = True
        
        # Create or get Basic plan
        basic_plan = SubscriptionPlan.query.filter_by(name='Basic').first()
        if not basic_plan:
            print("📋 Creating Basic subscription plan...")
            basic_plan = SubscriptionPlan(
                name='Basic',
                description='Basic SMS AI Plan',
                monthly_price=49.99,
                annual_price=499.99,
                currency='USD',
                trial_period_days=14,
                features={
                    'ai_responses_monthly': 1000,
                    'max_profiles': 1,
                    'max_phone_numbers': 1,
                    'storage_gb': 1,
                    'message_history_months': 12,
                    'advanced_analytics': False,
                    'priority_support': False,
                    'api_access': False,
                    'webhooks': True,
                    'custom_branding': False,
                    'team_collaboration': False,
                    'custom_ai_prompts': True,
                    'ai_personality_customization': True,
                    'advanced_ai_models': False,
                    'third_party_integrations': False,
                    'crm_integration': False,
                    'calendar_integration': False,
                    'rate_limit_per_minute': 60,
                    'concurrent_conversations': 10,
                    'available_addons': []
                },
                status='active'
            )
            db.session.add(basic_plan)
            db.session.flush()
        
        # Create active subscription for admin user
        subscription = Subscription.query.filter_by(user_id=admin_user.id).first()
        if not subscription:
            print("💳 Creating active subscription...")
            subscription = Subscription(
                user_id=admin_user.id,
                plan_id=basic_plan.id,
                status='active',
                billing_cycle='monthly',
                auto_renew=True,
                amount=basic_plan.monthly_price,
                current_period_start=datetime.utcnow(),
                current_period_end=datetime.utcnow() + timedelta(days=30),
                created_at=datetime.utcnow()
            )
            db.session.add(subscription)
        else:
            print("💳 Updating existing subscription...")
            subscription.status = 'active'
        
        # Create default payment method for admin user
        payment_method = PaymentMethod.query.filter_by(user_id=admin_user.id).first()
        if not payment_method:
            print("💳 Creating default payment method...")
            payment_method = PaymentMethod(
                user_id=admin_user.id,
                type='card',
                is_default=True,
                status='active',
                card_brand='visa',
                card_last4='4242',
                card_exp_month=12,
                card_exp_year=2025,
                created_at=datetime.utcnow()
            )
            db.session.add(payment_method)
        
        # Create additional test plans
        test_plans = [
            {
                'name': 'Professional',
                'description': 'Professional SMS AI Plan',
                'monthly_price': 99.99,
                'annual_price': 999.99,
                'features': {
                    'ai_responses_monthly': 5000,
                    'max_profiles': 3,
                    'max_phone_numbers': 3,
                    'storage_gb': 5,
                    'message_history_months': 24,
                    'advanced_analytics': True,
                    'priority_support': True,
                    'api_access': True,
                    'webhooks': True,
                    'custom_branding': True,
                    'team_collaboration': True,
                    'custom_ai_prompts': True,
                    'ai_personality_customization': True,
                    'advanced_ai_models': True,
                    'third_party_integrations': True,
                    'crm_integration': True,
                    'calendar_integration': True,
                    'rate_limit_per_minute': 120,
                    'concurrent_conversations': 50,
                    'available_addons': ['extra_numbers', 'premium_support']
                }
            },
            {
                'name': 'Enterprise',
                'description': 'Enterprise SMS AI Plan',
                'monthly_price': 249.99,
                'annual_price': 2499.99,
                'features': {
                    'ai_responses_monthly': 999999,
                    'max_profiles': 999,
                    'max_phone_numbers': 10,
                    'storage_gb': 50,
                    'message_history_months': 60,
                    'advanced_analytics': True,
                    'priority_support': True,
                    'api_access': True,
                    'webhooks': True,
                    'custom_branding': True,
                    'team_collaboration': True,
                    'custom_ai_prompts': True,
                    'ai_personality_customization': True,
                    'advanced_ai_models': True,
                    'third_party_integrations': True,
                    'crm_integration': True,
                    'calendar_integration': True,
                    'rate_limit_per_minute': 300,
                    'concurrent_conversations': 200,
                    'available_addons': ['dedicated_support', 'custom_integration']
                }
            }
        ]
        
        for plan_data in test_plans:
            existing_plan = SubscriptionPlan.query.filter_by(name=plan_data['name']).first()
            if not existing_plan:
                print(f"📋 Creating {plan_data['name']} plan...")
                plan = SubscriptionPlan(
                    name=plan_data['name'],
                    description=plan_data['description'],
                    monthly_price=plan_data['monthly_price'],
                    annual_price=plan_data['annual_price'],
                    currency='USD',
                    trial_period_days=14,
                    features=plan_data['features'],
                    status='active'
                )
                db.session.add(plan)
        
        # Create test users for development
        test_users_data = [
            {
                'username': 'testuser1',
                'email': 'test1@example.com',
                'phone': '+14165551234',
                'trial': True
            },
            {
                'username': 'testuser2', 
                'email': 'test2@example.com',
                'phone': '+16475551234',
                'trial': False
            }
        ]
        
        for user_data in test_users_data:
            existing_user = User.query.filter_by(email=user_data['email']).first()
            if not existing_user:
                print(f"👤 Creating test user: {user_data['username']}...")
                test_user = User(
                    username=user_data['username'],
                    email=user_data['email'],
                    password="password123"
                )
                test_user.first_name = "Test"
                test_user.last_name = "User"
                test_user.phone = user_data['phone']
                test_user.is_verified = True
                test_user.is_active = True
                test_user.ai_enabled = True
                
                if user_data['trial']:
                    test_user.trial_phone_expires_at = datetime.utcnow() + timedelta(days=14)
                    test_user.signalwire_phone_number = user_data['phone']
                    test_user.signalwire_setup_completed = True
                    test_user.signalwire_subproject_id = f"test_subproject_{user_data['username']}"
                    test_user.signalwire_subproject_token = f"test_token_{user_data['username']}"
                
                db.session.add(test_user)
                db.session.flush()
                
                # Create subscription for test user
                if user_data['trial']:
                    test_subscription = Subscription(
                        user_id=test_user.id,
                        plan_id=basic_plan.id,
                        status='trialing',
                        billing_cycle='monthly',
                        auto_renew=True,
                        amount=basic_plan.monthly_price,
                        current_period_start=datetime.utcnow(),
                        current_period_end=datetime.utcnow() + timedelta(days=14),
                        trial_end=datetime.utcnow() + timedelta(days=14),
                        created_at=datetime.utcnow()
                    )
                    db.session.add(test_subscription)
                    
                    # Add payment method for trial user
                    test_payment = PaymentMethod(
                        user_id=test_user.id,
                        type='card',
                        is_default=True,
                        status='active',
                        card_brand='visa',
                        card_last4='4242',
                        card_exp_month=12,
                        card_exp_year=2025,
                        created_at=datetime.utcnow()
                    )
                    db.session.add(test_payment)
        
        # Commit all changes
        db.session.commit()
        
        print("✅ Phone number initialization completed!")
        print(f"📞 Your phone number: {YOUR_PHONE}")
        print(f"👤 Admin user: {YOUR_EMAIL}")
        print(f"🔑 Admin password: admin123 (CHANGE THIS!)")
        print(f"💳 Subscription status: Active")
        print(f"⏰ Trial expires: {admin_user.trial_phone_expires_at}")
        print(f"📁 Backend location: {backend_path}")
        
        # Display all users
        print("\n👥 Users in system:")
        users = User.query.all()
        for user in users:
            subscription = user.current_subscription
            print(f"  - {user.username} ({user.email})")
            print(f"    Phone: {user.signalwire_phone_number or 'Not configured'}")
            print(f"    Status: {'Trial' if user.is_trial_user else 'Active' if subscription and subscription.status == 'active' else 'No subscription'}")
            print(f"    Trial expires: {user.trial_phone_expires_at or 'N/A'}")
            print()


if __name__ == "__main__":
    # Ensure we're in the right directory
    if not os.path.exists(os.path.join(backend_path, 'app')):
        print(f"❌ Backend not found at {backend_path}")
        print("Please ensure the backend is installed at /opt/assistext_backend")
        sys.exit(1)
    
    initialize_phone_number()
 
        # Create or get Basic plan
	basic_plan = SubscriptionPlan.query.filter_by(name='Basic').first()
        if not basic_plan:
            print("📋 Creating Basic subscription plan...")
            basic_plan = SubscriptionPlan(
                name='Basic',
                description='Basic SMS AI Plan',
                monthly_price=49.99,
                annual_price=499.99,
                currency='USD',
                trial_period_days=14,
                features={
                    'ai_responses_monthly': 1000,
                    'max_profiles': 1,
                    'max_phone_numbers': 1,
                    'storage_gb': 1,
                    'message_history_months': 12,
                    'advanced_analytics': False,
                    'priority_support': False,
                    'api_access': False,
                    'webhooks': True,
                    'custom_branding': False,
                    'team_collaboration': False,
                    'custom_ai_prompts': True,
                    'ai_personality_customization': True,
                    'advanced_ai_models': False,
                    'third_party_integrations': False,
                    'crm_integration': False,
                    'calendar_integration': False,
                    'rate_limit_per_minute': 60,
                    'concurrent_conversations': 10,
                    'available_addons': []
                },
                status='active'
            )
            db.session.add(basic_plan)
            db.session.flush()
        
        # Create active subscription for admin user
        subscription = Subscription.query.filter_by(user_id=admin_user.id).first()
        if not subscription:
            print("💳 Creating active subscription...")
            subscription = Subscription(
                user_id=admin_user.id,
                plan_id=basic_plan.id,
                status='active',
                billing_cycle='monthly',
                auto_renew=True,
                amount=basic_plan.monthly_price,
                current_period_start=datetime.utcnow(),
                current_period_end=datetime.utcnow() + timedelta(days=30),
                created_at=datetime.utcnow()
            )
            db.session.add(subscription)
        
        # Create default payment method for admin user
        payment_method = PaymentMethod.query.filter_by(user_id=admin_user.id).first()
        if not payment_method:
            print("💳 Creating default payment method...")
            payment_method = PaymentMethod(
                user_id=admin_user.id,
                type='card',
                is_default=True,
                status='active',
                card_brand='visa',
                card_last4='4242',
                card_exp_month=12,
                card_exp_year=2025,
                created_at=datetime.utcnow()
            )
            db.session.add(payment_method)
        
        # Create additional test plans
        test_plans = [
            {
                'name': 'Professional',
                'description': 'Professional SMS AI Plan',
                'monthly_price': 99.99,
                'annual_price': 999.99,
                'features': {
                    'ai_responses_monthly': 5000,
                    'max_profiles': 3,
                    'max_phone_numbers': 3,
                    'storage_gb': 5,
                    'message_history_months': 24,
                    'advanced_analytics': True,
                    'priority_support': True,
                    'api_access': True,
                    'webhooks': True,
                    'custom_branding': True,
                    'team_collaboration': True,
                    'custom_ai_prompts': True,
                    'ai_personality_customization': True,
                    'advanced_ai_models': True,
                    'third_party_integrations': True,
                    'crm_integration': True,
                    'calendar_integration': True,
                    'rate_limit_per_minute': 120,
                    'concurrent_conversations': 50,
                    'available_addons': ['extra_numbers', 'premium_support']
                }
            },
            {
                'name': 'Enterprise',
                'description': 'Enterprise SMS AI Plan',
                'monthly_price': 249.99,
                'annual_price': 2499.99,
                'features': {
                    'ai_responses_monthly': 999999,
                    'max_profiles': 999,
                    'max_phone_numbers': 10,
                    'storage_gb': 50,
                    'message_history_months': 60,
                    'advanced_analytics': True,
                    'priority_support': True,
                    'api_access': True,
                    'webhooks': True,
                    'custom_branding': True,
                    'team_collaboration': True,
                    'custom_ai_prompts': True,
                    'ai_personality_customization': True,
                    'advanced_ai_models': True,
                    'third_party_integrations': True,
                    'crm_integration': True,
                    'calendar_integration': True,
                    'rate_limit_per_minute': 300,
                    'concurrent_conversations': 200,
                    'available_addons': ['dedicated_support', 'custom_integration']
                }
            }
        ]
        
        for plan_data in test_plans:
            existing_plan = SubscriptionPlan.query.filter_by(name=plan_data['name']).first()
            if not existing_plan:
                print(f"📋 Creating {plan_data['name']} plan...")
                plan = SubscriptionPlan(
                    name=plan_data['name'],
                    description=plan_data['description'],
                    monthly_price=plan_data['monthly_price'],
                    annual_price=plan_data['annual_price'],
                    currency='USD',
                    trial_period_days=14,
                    features=plan_data['features'],
                    status='active'
                )
                db.session.add(plan)
        
        # Create test users for development
        test_users_data = [
            {
                'username': 'testuser1',
                'email': 'test1@example.com',
                'phone': '+14165551234',
                'trial': True
            },
            {
                'username': 'testuser2', 
                'email': 'test2@example.com',
                'phone': '+16475551234',
                'trial': False
            }
        ]
        
        for user_data in test_users_data:
            existing_user = User.query.filter_by(email=user_data['email']).first()
            if not existing_user:
                print(f"👤 Creating test user: {user_data['username']}...")
                test_user = User(
                    username=user_data['username'],
                    email=user_data['email'],
                    password="password123"
                )
                test_user.first_name = "Test"
                test_user.last_name = "User"
                test_user.phone = user_data['phone']
                test_user.is_verified = True
                test_user.is_active = True
                test_user.ai_enabled = True
                
                if user_data['trial']:
                    test_user.trial_phone_expires_at = datetime.utcnow() + timedelta(days=14)
                    test_user.signalwire_phone_number = user_data['phone']
                    test_user.signalwire_setup_completed = True
                    test_user.signalwire_subproject_id = f"test_subproject_{user_data['username']}"
                    test_user.signalwire_subproject_token = f"test_token_{user_data['username']}"
                
                db.session.add(test_user)
                db.session.flush()
                
                # Create subscription for test user
                if user_data['trial']:
                    test_subscription = Subscription(
                        user_id=test_user.id,
                        plan_id=basic_plan.id,
                        status='trialing',
                        billing_cycle='monthly',
                        auto_renew=True,
                        amount=basic_plan.monthly_price,
                        current_period_start=datetime.utcnow(),
                        current_period_end=datetime.utcnow() + timedelta(days=14),
                        trial_end=datetime.utcnow() + timedelta(days=14),
                        created_at=datetime.utcnow()
                    )
                    db.session.add(test_subscription)
        
        # Commit all changes
        db.session.commit()
        
        print("✅ Phone number initialization completed!")
        print(f"📞 Your phone number: {YOUR_PHONE}")
        print(f"👤 Admin user: {YOUR_EMAIL}")
        print(f"🔑 Admin password: admin123 (CHANGE THIS!)")
        print(f"💳 Subscription status: Active")
        print(f"⏰ Trial expires: {admin_user.trial_phone_expires_at}")
        
        # Display all users
        print("\n👥 Users in system:")
        users = User.query.all()
        for user in users:
            subscription = user.current_subscription
            print(f"  - {user.username} ({user.email})")
            print(f"    Phone: {user.signalwire_phone_number or 'Not configured'}")
            print(f"    Status: {'Trial' if user.is_trial_user else 'Active' if subscription and subscription.status == 'active' else 'No subscription'}")
            print(f"    Trial expires: {user.trial_phone_expires_at or 'N/A'}")
            print()


if __name__ == "__main__":
    initialize_phone_number()

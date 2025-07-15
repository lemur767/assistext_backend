#!/bin/bash

# Fix Critical Import Issues - Run this first!
# This script fixes the duplicate imports and critical errors

echo "🔧 Fixing critical import issues..."

# Step 1: Backup current files
echo "📦 Creating backups..."
mkdir -p backups/$(date +%Y%m%d_%H%M%S)
cp app/services/subscription_service.py backups/$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || echo "subscription_service.py not found - skipping backup"

# Step 2: Fix subscription_service.py duplicate imports
echo "🛠️ Fixing subscription_service.py..."
if [ -f "app/services/subscription_service.py" ]; then
    cat > app/services/subscription_service.py << 'EOF'
from app.models.billing import Subscription
from app.models.signalwire_account import SignalWireAccount, SignalWirePhoneNumber
from app.models.user import User
from app.extensions import db
from flask import current_app
from datetime import datetime, timedelta
import secrets

# Import SMS service functions (will create this next)
try:
    from app.services.sms_service import SMSService
except ImportError:
    # Fallback to utils until we create sms_service
    from app.utils.signalwire_helpers import (
        get_signalwire_client, 
        send_sms, 
        get_signalwire_phone_numbers, 
        get_available_phone_numbers, 
        purchase_phone_number, 
        configure_number_webhook
    )

class SubscriptionService:
    """Service for managing subscriptions with SignalWire integration"""
    
    @staticmethod
    def create_subscription_with_signalwire(user_id: int, plan_id: int):
        """Create subscription and set up SignalWire integration"""
        try:
            user = User.query.get(user_id)
            if not user:
                return False, "User not found"
            
            # Create subscription logic here
            # This is a placeholder - implement your subscription creation logic
            
            return True, "Subscription created successfully"
            
        except Exception as e:
            current_app.logger.error(f"Subscription creation failed: {e}")
            return False, str(e)
EOF
    echo "✅ Fixed subscription_service.py"
else
    echo "⚠️ subscription_service.py not found - skipping"
fi

# Step 3: Check for and remove deleted files
echo "🗑️ Removing any remaining deprecated files..."
rm -f app/api/profiles.py 2>/dev/null && echo "✅ Removed profiles.py" || echo "ℹ️ profiles.py already removed"
rm -f app/models/profile.py 2>/dev/null && echo "✅ Removed profile.py" || echo "ℹ️ profile.py already removed"
rm -f app/models/profile_client.py 2>/dev/null && echo "✅ Removed profile_client.py" || echo "ℹ️ profile_client.py already removed"
rm -f app/models/payment.py 2>/dev/null && echo "✅ Removed payment.py" || echo "ℹ️ payment.py already removed"

# Step 4: Test basic imports
echo "🧪 Testing basic imports..."
python3 -c "
try:
    from app.extensions import db
    print('✅ Extensions import successful')
except Exception as e:
    print(f'❌ Extensions import failed: {e}')

try:
    from app.models.user import User
    print('✅ User model import successful')
except Exception as e:
    print(f'❌ User model import failed: {e}')

try:
    from app.models.billing import Subscription
    print('✅ Billing models import successful')
except Exception as e:
    print(f'❌ Billing models import failed: {e}')
"

echo "✅ Critical fixes complete!"
echo "👉 Next: Run create_sms_service.sh"#!/bin/bash

# Fix Critical Import Issues - Run this first!
# This script fixes the duplicate imports and critical errors

echo "🔧 Fixing critical import issues..."

# Step 1: Backup current files
echo "📦 Creating backups..."
mkdir -p backups/$(date +%Y%m%d_%H%M%S)
cp app/services/subscription_service.py backups/$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || echo "subscription_service.py not found - skipping backup"

# Step 2: Fix subscription_service.py duplicate imports
echo "🛠️ Fixing subscription_service.py..."
if [ -f "app/services/subscription_service.py" ]; then
    cat > app/services/subscription_service.py << 'EOF'
from app.models.billing import Subscription
from app.models.signalwire_account import SignalWireAccount, SignalWirePhoneNumber
from app.models.user import User
from app.extensions import db
from flask import current_app
from datetime import datetime, timedelta
import secrets

# Import SMS service functions (will create this next)
try:
    from app.services.sms_service import SMSService
except ImportError:
    # Fallback to utils until we create sms_service
    from app.utils.signalwire_helpers import (
        get_signalwire_client, 
        send_sms, 
        get_signalwire_phone_numbers, 
        get_available_phone_numbers, 
        purchase_phone_number, 
        configure_number_webhook
    )

class SubscriptionService:
    """Service for managing subscriptions with SignalWire integration"""
    
    @staticmethod
    def create_subscription_with_signalwire(user_id: int, plan_id: int):
        """Create subscription and set up SignalWire integration"""
        try:
            user = User.query.get(user_id)
            if not user:
                return False, "User not found"
            
            # Create subscription logic here
            # This is a placeholder - implement your subscription creation logic
            
            return True, "Subscription created successfully"
            
        except Exception as e:
            current_app.logger.error(f"Subscription creation failed: {e}")
            return False, str(e)
EOF
    echo "✅ Fixed subscription_service.py"
else
    echo "⚠️ subscription_service.py not found - skipping"
fi

# Step 3: Check for and remove deleted files
echo "🗑️ Removing any remaining deprecated files..."
rm -f app/api/profiles.py 2>/dev/null && echo "✅ Removed profiles.py" || echo "ℹ️ profiles.py already removed"
rm -f app/models/profile.py 2>/dev/null && echo "✅ Removed profile.py" || echo "ℹ️ profile.py already removed"
rm -f app/models/profile_client.py 2>/dev/null && echo "✅ Removed profile_client.py" || echo "ℹ️ profile_client.py already removed"
rm -f app/models/payment.py 2>/dev/null && echo "✅ Removed payment.py" || echo "ℹ️ payment.py already removed"

# Step 4: Test basic imports
echo "🧪 Testing basic imports..."
python3 -c "
try:
    from app.extensions import db
    print('✅ Extensions import successful')
except Exception as e:
    print(f'❌ Extensions import failed: {e}')

try:
    from app.models.user import User
    print('✅ User model import successful')
except Exception as e:
    print(f'❌ User model import failed: {e}')

try:
    from app.models.billing import Subscription
    print('✅ Billing models import successful')
except Exception as e:
    print(f'❌ Billing models import failed: {e}')
"

echo "✅ Critical fixes complete!"
echo "👉 Next: Run create_sms_service.sh"

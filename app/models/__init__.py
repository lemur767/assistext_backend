def init_models():
    """Initialize all models - import them to register with SQLAlchemy"""
    
    # Core models
    from app.models.user import User
    from app.models.profile import Profile
    from app.models.client import Client
    from app.models.profile_client import ProfileClient
    
    # Billing and subscription models
    from app.models.billing import SubscriptionPlan, Subscription, Invoice, InvoiceItem
    from app.models.payment import PaymentMethod
    from app.models.subscription_payment_method import SubscriptionPaymentMethod
    
    # Messaging models
    from app.models.message import Message
    from app.models.flagged_message import FlaggedMessage
    from app.models.text_example import TextExample
    from app.models.auto_reply import AutoReply, OutOfOfficeReply
    
    # AI and settings models
    from app.models.ai_model_settings import AIModelSettings
    from app.models.banned_words import BannedWord
    
    # Usage and tracking models
    from app.models.usage import UsageRecord, ActivityLog
    from app.models.twilio_usage import TwilioUsage
    
    # API and utility models
    from app.models.api_key import APIKey
    
    # Store in globals for backward compatibility
    globals()['User'] = User
    globals()['Profile'] = Profile
    globals()['Client'] = Client
    globals()['ProfileClient'] = ProfileClient
    globals()['SubscriptionPlan'] = SubscriptionPlan
    globals()['Subscription'] = Subscription
    globals()['Invoice'] = Invoice
    globals()['InvoiceItem'] = InvoiceItem
    globals()['PaymentMethod'] = PaymentMethod
    globals()['SubscriptionPaymentMethod'] = SubscriptionPaymentMethod
    globals()['Message'] = Message
    globals()['FlaggedMessage'] = FlaggedMessage
    globals()['TextExample'] = TextExample
    globals()['AutoReply'] = AutoReply
    globals()['OutOfOfficeReply'] = OutOfOfficeReply
    globals()['AIModelSettings'] = AIModelSettings
    globals()['BannedWord'] = BannedWord
    globals()['UsageRecord'] = UsageRecord
    globals()['ActivityLog'] = ActivityLog
    globals()['TwilioUsage'] = TwilioUsage
    globals()['APIKey'] = APIKey
    
    # Return models dict for easy access
    return {
        'User': User,
        'Profile': Profile,
        'Client': Client,
        'ProfileClient': ProfileClient,
        'SubscriptionPlan': SubscriptionPlan,
        'Subscription': Subscription,
        'Invoice': Invoice,
        'InvoiceItem': InvoiceItem,
        'PaymentMethod': PaymentMethod,
        'SubscriptionPaymentMethod': SubscriptionPaymentMethod,
        'Message': Message,
        'FlaggedMessage': FlaggedMessage,
        'TextExample': TextExample,
        'AutoReply': AutoReply,
        'OutOfOfficeReply': OutOfOfficeReply,
        'AIModelSettings': AIModelSettings,
        'BannedWord': BannedWord,
        'UsageRecord': UsageRecord,
        'ActivityLog': ActivityLog,
        'TwilioUsage': TwilioUsage,
        'APIKey': APIKey,
    }

# For backward compatibility
models = None

def get_models():
    """Get all models as a dictionary"""
    global models
    if models is None:
        models = init_models()
    return models

from app.extensions import db
from datetime import datetime

class SubscriptionPaymentMethod(db.Model):
    __tablename__ = 'subscription_payment_methods'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'), nullable=False)
    payment_method_id = db.Column(db.Integer, db.ForeignKey('payment_methods.id'), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('subscription_id', 'payment_method_id', name='uix_sub_payment_method'),
    )
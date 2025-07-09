"""
Database model for credit transactions
"""

from app.extensions import db
from datetime import datetime

class CreditTransaction(db.Model):
    """Credit transaction model"""
    __tablename__ = 'credit_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Transaction details
    type = db.Column(db.String(20), nullable=False)  # credit, debit, refund, bonus, adjustment, expiration
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='USD')
    balance_after = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Details
    description = db.Column(db.Text, nullable=False)
    reference_id = db.Column(db.String(50))  # Reference to payment, refund, etc.
    reference_type = db.Column(db.String(20))  # payment, refund, adjustment, bonus
    
    # Expiration
    expires_at = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    
    # Metadata
    trans_metadata = db.Column(db.JSON)
    
    # Relationships
    user = db.relationship('User', backref='credit_transactions')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'type': self.type,
            'amount': float(self.amount),
            'currency': self.currency,
            'balance_after': float(self.balance_after),
            'description': self.description,
            'reference_id': self.reference_id,
            'reference_type': self.reference_type,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'trans_metadata': self.trans_metadata
        }
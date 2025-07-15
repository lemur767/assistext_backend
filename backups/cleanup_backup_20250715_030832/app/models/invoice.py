


from app.extensions import db
from datetime import datetime

class Invoice(db.Model):
    """Invoice model"""
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subscription_id = db.Column(db.Integer), db.ForeignKey('subscriptions.id'))
    
    # Invoice details
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # draft, open, paid, void, uncollectible
    
    # Amounts
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(10, 2), default=0.0)
    discount_amount = db.Column(db.Numeric(10, 2), default=0.0)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    amount_paid = db.Column(db.Numeric(10, 2), default=0.0)
    amount_due = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='USD')
    
    # Dates
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    due_date = db.Column(db.DateTime)
    paid_at = db.Column(db.DateTime)
    
    # Files
    pdf_url = db.Column(db.String(255))
    
    # Payment processor reference
    stripe_invoice_id = db.Column(db.String(100))
    
    # Metadata
    description = db.Column(db.Text)
    invoice_metadata = db.Column(db.JSON)
    
    # Relationships
    user = db.relationship('User', backref='invoices')
    line_items = db.relationship('InvoiceLineItem', backref='invoice', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self, include_relationships=False):
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'subscription_id': self.subscription_id,
            'invoice_number': self.invoice_number,
            'status': self.status,
            'subtotal': float(self.subtotal),
            'tax_amount': float(self.tax_amount) if self.tax_amount else 0.0,
            'discount_amount': float(self.discount_amount) if self.discount_amount else 0.0,
            'total': float(self.total),
            'amount_paid': float(self.amount_paid) if self.amount_paid else 0.0,
            'amount_due': float(self.amount_due),
            'currency': self.currency,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'pdf_url': self.pdf_url,
            'description': self.description,
            'invoice_metadata': self.invoice_metadata
        }
        
        if include_relationships:
            data['line_items'] = [item.to_dict() for item in self.line_items]
            data['payments'] = [payment.to_dict() for payment in self.payments]
        
        return data


class InvoiceLineItem(db.Model):
    """Invoice line item model"""
    __tablename__ = 'invoice_line_items'
    
    id = db.Column(db.String(50), primary_key=True)
    invoice_id = db.Column(db.String(50), db.ForeignKey('invoices.id'), nullable=False)
    
    # Line item details
    description = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_amount = db.Column(db.Numeric(10, 2), nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Period for subscription items
    period_start = db.Column(db.DateTime)
    period_end = db.Column(db.DateTime)
    proration = db.Column(db.Boolean, default=False)
    
    # Metadata
    invoice_item_metadata = db.Column(db.JSON)
    
    def to_dict(self):
        return {
            'id': self.id,
            'invoice_id': self.invoice_id,
            'description': self.description,
            'quantity': self.quantity,
            'unit_amount': float(self.unit_amount),
            'total_amount': float(self.total_amount),
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'proration': self.proration,
            'invoice_item_metadata': self.invoice_item_metadata
        }

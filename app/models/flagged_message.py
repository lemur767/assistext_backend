from app.extensions import db
from datetime import datetime


class FlaggedMessage(db.Model):
    __tablename__ = 'flagged_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=False)
    reasons = db.Column(db.Text, nullable=False)  # JSON array of reasons
    severity = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    is_reviewed = db.Column(db.Boolean, default=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    review_notes = db.Column(db.Text)
    
    # Automated detection info
    detection_method = db.Column(db.String(50))  # keyword, pattern, ai, manual
    confidence_score = db.Column(db.Float)  # 0.0 to 1.0
    
    # Response handling
    response_blocked = db.Column(db.Boolean, default=False)
    auto_response_sent = db.Column(db.String(500))  # If auto-response was triggered
    
    flagged_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    
    # Relationships
    message = db.relationship('Message', back_populates='flagged_details')
    reviewer = db.relationship('User', foreign_keys=[reviewer_id])
    
    def get_reasons(self):
        """Parse JSON reasons into list"""
        if self.reasons:
            import json
            try:
                return json.loads(self.reasons)
            except:
                return [self.reasons]
        return []
    
    def set_reasons(self, reasons_list):
        """Set reasons from list"""
        import json
        self.reasons = json.dumps(reasons_list)
    
    def to_dict(self):
        return {
            'id': self.id,
            'message_id': self.message_id,
            'reasons': self.get_reasons(),
            'severity': self.severity,
            'is_reviewed': self.is_reviewed,
            'review_notes': self.review_notes,
            'detection_method': self.detection_method,
            'confidence_score': self.confidence_score,
            'response_blocked': self.response_blocked,
            'flagged_at': self.flagged_at.isoformat(),
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None
        }

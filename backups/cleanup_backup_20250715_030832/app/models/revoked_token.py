# app/models/revoked_token.py
from app.extensions import db
from datetime import datetime

class RevokedToken(db.Model):
    __tablename__ = 'revoked_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(120), nullable=False, unique=True)
    revoked_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    
    def __repr__(self):
        return f'<RevokedToken {self.jti}>'
    
    @classmethod
    def is_token_revoked(cls, jti):
        """Check if a token is revoked"""
        return cls.query.filter_by(jti=jti).first() is not None
    
    @classmethod
    def revoke_token(cls, jti, expires_at):
        """Revoke a token"""
        revoked_token = cls(jti=jti, expires_at=expires_at)
        db.session.add(revoked_token)
        db.session.commit()
        return revoked_token
    
    @classmethod
    def clean_expired_tokens(cls):
        """Remove expired tokens from the database"""
        cls.query.filter(cls.expires_at < datetime.utcnow()).delete()
        db.session.commit()
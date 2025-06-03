from app.extensions import db
from datetime import datetime

class AIModelSettings(db.Model):
    __tablename__ = 'ai_model_settings'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False)
    model_version = db.Column(db.String(50), default='gpt-4')
    temperature = db.Column(db.Numeric(3, 2), default=0.7)
    response_length = db.Column(db.Integer, default=150)
    style_notes = db.Column(db.Text)
    custom_instructions = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    profile = db.relationship('Profile', back_populates='ai_model_settings')
    
    def to_dict(self):
        """Convert AI model settings to dictionary"""
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'model_version': self.model_version,
            'temperature': float(self.temperature),
            'response_length': self.response_length,
            'style_notes': self.style_notes,
            'custom_instructions': self.custom_instructions,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def get_system_prompt(self, client=None):
        """Generate system prompt for OpenAI API"""
        prompt = f"""
        You are responding as {self.profile.name}, an escort. Mimic their texting style based on previous examples.
        
        Guidelines:
        1. Keep the same writing style, capitalization, and punctuation as in the examples
        2. Keep responses brief and natural, like actual text messages (1-3 sentences max)
        3. NEVER explicitly mention prices or specific services
        4. Be friendly but professional
        5. For scheduling requests, suggest continuing the conversation but don't make firm commitments
        6. If someone asks about location, suggest they should discuss details later
        7. Don't mention that you're an AI - respond as if you're the actual person
        8. If the message contains suspicious content like law enforcement terms, respond vaguely or change the subject
        """
        
        # Add client-specific information if available
        if client and client.notes:
            prompt += f"\nClient information: {client.notes}\n"
        
        # Add custom instructions if available
        if self.custom_instructions:
            prompt += f"\n{self.custom_instructions}\n"
        
        # Add style notes if available
        if self.style_notes:
            prompt += f"\nStyle notes: {self.style_notes}\n"
        
        return prompt.strip()


class BannedWord(db.Model):
    __tablename__ = 'banned_words'
    
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(50), unique=True, nullable=False)
    category = db.Column(db.String(50))  # 'law_enforcement', 'explicit', 'illegal'
    severity = db.Column(db.Integer, default=1)  # 1-5 scale
    action = db.Column(db.String(20), default='flag')  # 'flag', 'block', 'ignore'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def check_message(cls, message_text):
        """Check message against banned words"""
        message_lower = message_text.lower()
        matched_words = []
        
        banned_words = cls.query.all()
        for banned in banned_words:
            if banned.word.lower() in message_lower:
                matched_words.append({
                    'word': banned.word,
                    'category': banned.category,
                    'severity': banned.severity,
                    'action': banned.action
                })
        
        return matched_words
    
    def to_dict(self):
        """Convert banned word to dictionary"""
        return {
            'id': self.id,
            'word': self.word,
            'category': self.category,
            'severity': self.severity,
            'action': self.action,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
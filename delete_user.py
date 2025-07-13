#!/usr/bin/env python3
import sys
sys.path.insert(0, '/opt/assistext_backend')

from app import create_app
from app.extensions import db
from app.models.user import User

def delete_user_by_id(user_id):
    app = create_app()
    with app.app_context():
        user = db.session.get(User, user_id)
        if user:
            print(f"Deleting user: {user.username}")
            db.session.delete(user)
            db.session.commit()
            print("✅ User deleted successfully")
        else:
            print("❌ User not found")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python delete_user.py <user_id>")
        sys.exit(1)
    
    user_id = int(sys.argv[1])
    delete_user_by_id(user_id)

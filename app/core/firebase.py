"""Firebase configuration and initialization"""

import firebase_admin
from firebase_admin import credentials, messaging
import json
import os
from typing import Optional

from app.core.config import settings

# Initialize Firebase Admin SDK
firebase_app: Optional[firebase_admin.App] = None

def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    global firebase_app
    
    if firebase_app:
        return firebase_app
    
    try:
        # Try to load credentials from environment variable
        if settings.FIREBASE_CREDENTIALS_JSON:
            cred_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
            cred = credentials.Certificate(cred_dict)
        # Or from file path
        elif settings.FIREBASE_CREDENTIALS_PATH:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        else:
            raise ValueError("Firebase credentials not configured")
            
        firebase_app = firebase_admin.initialize_app(cred)
        return firebase_app
        
    except Exception as e:
        print(f"Failed to initialize Firebase: {e}")
        return None

# Initialize on module import
initialize_firebase()

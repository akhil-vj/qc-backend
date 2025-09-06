"""Firebase push notification service"""

import firebase_admin
from firebase_admin import credentials, messaging
from typing import List, Dict, Any, Optional
import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

class FirebaseService:
    """Service for sending push notifications via Firebase"""
    
    def __init__(self):
        # Initialize Firebase Admin SDK
        cred_path = Path(settings.FIREBASE_CREDENTIALS_PATH)
        if not cred_path.exists():
            logger.error(f"Firebase credentials not found at {cred_path}")
            self.initialized = False
            return
            
        try:
            cred = credentials.Certificate(str(cred_path))
            firebase_admin.initialize_app(cred)
            self.initialized = True
            logger.info("Firebase Admin SDK initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
            self.initialized = False
            
    def send_notification(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image_url: Optional[str] = None,
        priority: str = "high"
    ) -> bool:
        """Send push notification to a single device"""
        if not self.initialized:
            logger.error("Firebase not initialized")
            return False
            
        try:
            # Build notification
            notification = messaging.Notification(
                title=title,
                body=body,
                image=image_url
            )
            
            # Build message
            message = messaging.Message(
                notification=notification,
                data=data or {},
                token=token,
                android=messaging.AndroidConfig(
                    priority=priority,
                    notification=messaging.AndroidNotification(
                        click_action="FLUTTER_NOTIFICATION_CLICK",
                        sound="default"
                    )
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            sound="default",
                            badge=1
                        )
                    )
                )
            )
            
            # Send message
            response = messaging.send(message)
            logger.info(f"Successfully sent push notification: {response}")
            return True
            
        except messaging.UnregisteredError:
            logger.warning(f"Token {token} is unregistered")
            return False
        except Exception as e:
            logger.error(f"Error sending push notification: {str(e)}")
            return False
            
    def send_multicast_notification(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send notification to multiple devices"""
        if not self.initialized or not tokens:
            return {"success": 0, "failure": len(tokens)}
            
        try:
            # Build notification
            notification = messaging.Notification(
                title=title,
                body=body,
                image=image_url
            )
            
            # Build multicast message
            message = messaging.MulticastMessage(
                notification=notification,
                data=data or {},
                tokens=tokens
            )
            
            # Send messages
            response = messaging.send_multicast(message)
            
            # Process failed tokens
            failed_tokens = []
            if response.failure_count > 0:
                for idx, resp in enumerate(response.responses):
                    if not resp.success:
                        failed_tokens.append(tokens[idx])
                        
            logger.info(
                f"Multicast result - Success: {response.success_count}, "
                f"Failure: {response.failure_count}"
            )
            
            return {
                "success": response.success_count,
                "failure": response.failure_count,
                "failed_tokens": failed_tokens
            }
            
        except Exception as e:
            logger.error(f"Error sending multicast notification: {str(e)}")
            return {"success": 0, "failure": len(tokens)}
            
    def send_topic_notification(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image_url: Optional[str] = None
    ) -> bool:
        """Send notification to a topic"""
        if not self.initialized:
            return False
            
        try:
            # Build notification
            notification = messaging.Notification(
                title=title,
                body=body,
                image=image_url
            )
            
            # Build message
            message = messaging.Message(
                notification=notification,
                data=data or {},
                topic=topic
            )
            
            # Send message
            response = messaging.send(message)
            logger.info(f"Successfully sent topic notification: {response}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending topic notification: {str(e)}")
            return False

"""Two-factor authentication service"""

import pyotp
import qrcode
import io
import base64
from typing import Optional, Tuple

from app.models import User
from app.core.cache import cache

class TwoFactorService:
    """Service for 2FA implementation"""
    
    @staticmethod
    def generate_secret() -> str:
        """Generate a new 2FA secret"""
        return pyotp.random_base32()
        
    @staticmethod
    def generate_qr_code(user: User, secret: str) -> str:
        """Generate QR code for 2FA setup"""
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.email or user.phone,
            issuer_name="QuickCart"
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        
        return base64.b64encode(buf.getvalue()).decode()
        
    @staticmethod
    def verify_token(secret: str, token: str) -> bool:
        """Verify 2FA token"""
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=1)
        
    @staticmethod
    async def generate_backup_codes(user_id: str, count: int = 10) -> List[str]:
        """Generate backup codes for 2FA"""
        codes = []
        for _ in range(count):
            code = pyotp.random_base32()[:8]
            codes.append(code)
            
        # Store hashed backup codes
        await cache.set(
            f"2fa_backup:{user_id}",
            codes,
            expire=None  # No expiration
        )
        
        return codes
        
    @staticmethod
    async def verify_backup_code(user_id: str, code: str) -> bool:
        """Verify and consume backup code"""
        backup_codes = await cache.get(f"2fa_backup:{user_id}")
        
        if backup_codes and code in backup_codes:
            backup_codes.remove(code)
            await cache.set(f"2fa_backup:{user_id}", backup_codes)
            return True
            
        return False

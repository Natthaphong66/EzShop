"""
Agora RTC Token Generation Service
"""
import hmac
import hashlib
import base64
import json
from django.conf import settings
from django.utils import timezone


class AccessToken:
    """Agora Access Token builder"""
    
    def __init__(self, app_id, app_certificate, channel_name, uid):
        self.app_id = app_id
        self.app_certificate = app_certificate
        self.channel_name = channel_name
        self.uid = uid
        self.messages = {}
    
    def add_privilege(self, privilege, expire_timestamp):
        self.messages[privilege] = expire_timestamp
    
    def build(self):
        m = {
            "app_id": self.app_id,
            "app_certificate": self.app_certificate,
            "channel_name": self.channel_name,
            "uid": str(self.uid),
            "privileges": self.messages
        }
        
        content = base64.b64encode(json.dumps(m, separators=(',', ':')).encode('utf-8')).decode('utf-8')
        
        version = "007"
        signature = self._hmacsha256(self.app_certificate, content)
        
        result = version + signature + content
        return result
    
    @staticmethod
    def _hmacsha256(key, message):
        return hmac.new(key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()


class RtcTokenBuilder:
    """Agora RTC Token Builder"""
    
    ROLE_PUBLISHER = 1
    ROLE_SUBSCRIBER = 2
    
    PRIVILEGE_JOIN_CHANNEL = 1
    PRIVILEGE_PUBLISH_AUDIO_STREAM = 2
    PRIVILEGE_PUBLISH_VIDEO_STREAM = 3
    PRIVILEGE_PUBLISH_DATA_STREAM = 4
    
    @staticmethod
    def buildTokenWithAccount(app_id, app_certificate, channel_name, account, role, expire_timestamp):
        """
        Build token with string account
        """
        # Convert account to integer UID (simple hash)
        uid = int(hashlib.md5(account.encode('utf-8')).hexdigest()[:8], 16) & 0x7FFFFFFF
        return RtcTokenBuilder.buildTokenWithUid(app_id, app_certificate, channel_name, uid, role, expire_timestamp)
    
    @staticmethod
    def buildTokenWithUid(app_id, app_certificate, channel_name, uid, role, expire_timestamp):
        """
        Build token with integer UID
        """
        token = AccessToken(app_id, app_certificate, channel_name, uid)
        
        # Add join channel privilege
        token.add_privilege(RtcTokenBuilder.PRIVILEGE_JOIN_CHANNEL, expire_timestamp)
        
        # Add publish privileges if role is publisher
        if role == RtcTokenBuilder.ROLE_PUBLISHER:
            token.add_privilege(RtcTokenBuilder.PRIVILEGE_PUBLISH_AUDIO_STREAM, expire_timestamp)
            token.add_privilege(RtcTokenBuilder.PRIVILEGE_PUBLISH_VIDEO_STREAM, expire_timestamp)
            token.add_privilege(RtcTokenBuilder.PRIVILEGE_PUBLISH_DATA_STREAM, expire_timestamp)
        
        return token.build()


def generate_rtc_token_with_account(account, channel_name, role="publisher", expire_time=3600):
    """
    Generate Agora RTC Token with string account (instead of integer UID)
    
    Args:
        account: String account identifier (usually user ID or username)
        channel_name: Channel name (usually stream channel name)
        role: "publisher" or "subscriber" (default: "publisher")
        expire_time: Token expiration time in seconds (default: 1 hour)
    
    Returns:
        str: RTC Token string
    """
    app_id = settings.AGORA_APP_ID
    app_certificate = settings.AGORA_APP_CERTIFICATE
    
    if not app_id or not app_certificate:
        raise ValueError("AGORA_APP_ID and AGORA_APP_CERTIFICATE must be set in settings")
    
    # Set role
    role_value = RtcTokenBuilder.ROLE_PUBLISHER if role == "publisher" else RtcTokenBuilder.ROLE_SUBSCRIBER
    
    # Calculate expiration time (Unix timestamp)
    current_timestamp = int(timezone.now().timestamp())
    expire_timestamp = current_timestamp + expire_time
    
    # Build token with account
    token = RtcTokenBuilder.buildTokenWithAccount(
        app_id,
        app_certificate,
        channel_name,
        account,
        role_value,
        expire_timestamp
    )
    
    return token


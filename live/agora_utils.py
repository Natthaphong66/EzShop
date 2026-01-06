from agora_token_builder import RtcTokenBuilder
from django.conf import settings
from datetime import datetime


def generate_agora_token(channel_name, uid=0, role=1, expiration_time=3600):
    """
    Generate Agora RTC token
    
    Args:
        channel_name: Channel name for the stream
        uid: User ID (0 for auto-assign)
        role: 1 for publisher, 2 for subscriber
        expiration_time: Token expiration in seconds (default 1 hour)
    
    Returns:
        str: Agora RTC token
    
    Raises:
        ValueError: If Agora credentials are not configured
    """
    try:
        app_id = getattr(settings, 'AGORA_APP_ID', None)
        app_certificate = getattr(settings, 'AGORA_APP_CERTIFICATE', None)
        
        if not app_id or not app_certificate:
            raise ValueError("Agora credentials are not configured. Please set AGORA_APP_ID and AGORA_APP_CERTIFICATE in .env file")
        
        current_timestamp = int(datetime.now().timestamp())
        privilege_expired_ts = current_timestamp + expiration_time
        
        token = RtcTokenBuilder.buildTokenWithUid(
            appId=app_id,
            appCertificate=app_certificate,
            channelName=channel_name,
            uid=uid,
            role=role,
            privilegeExpiredTs=privilege_expired_ts
        )
        
        return token
    except AttributeError as e:
        raise ValueError(f"Agora settings not found: {str(e)}")
    except Exception as e:
        raise ValueError(f"Failed to generate Agora token: {str(e)}")


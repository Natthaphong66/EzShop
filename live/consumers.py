import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone


class LiveChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for live stream chat"""
    
    async def connect(self):
        try:
            self.channel_name_param = self.scope['url_route']['kwargs']['channel_name']
            self.room_group_name = f'live_chat_{self.channel_name_param}'
            
            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            await self.accept()
        except Exception as e:
            print(f"LiveChatConsumer connect error: {e}")
            await self.close()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Receive message from WebSocket"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'chat_message')
            
            if message_type == 'chat_message':
                message = data.get('message', '').strip()
                user = self.scope.get('user')
                
                if not message or not user or not user.is_authenticated:
                    return
                
                # Get user profile picture URL
                profile_picture_url = None
                if user.profile_picture:
                    profile_picture_url = user.profile_picture.url
                
                # Broadcast message to room group
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': message,
                        'username': user.get_full_name_display(),
                        'user_id': str(user.id),
                        'profile_picture': profile_picture_url,
                        'timestamp': timezone.now().isoformat(),
                    }
                )
                
        except json.JSONDecodeError:
            pass
    
    async def chat_message(self, event):
        """Receive message from room group and send to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message'],
            'username': event['username'],
            'user_id': event['user_id'],
            'profile_picture': event.get('profile_picture'),
            'timestamp': event['timestamp'],
        }))

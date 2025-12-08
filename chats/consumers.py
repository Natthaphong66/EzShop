import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time chat"""

    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        self.user = self.scope['user']

        # Check if user is authenticated
        if not self.user.is_authenticated:
            await self.close()
            return

        # Check if user is a participant of the room
        is_participant = await self.check_room_participant()
        if not is_participant:
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Receive message from WebSocket"""
        data = json.loads(text_data)
        message_type = data.get('type', 'chat_message')

        if message_type == 'chat_message':
            content = data.get('content', '').strip()
            if content:
                # Save message to database
                message_data = await self.save_message(content)

                # Send message to room group
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': message_data
                    }
                )

    async def chat_message(self, event):
        """Receive message from room group and send to WebSocket"""
        message = event['message']
        
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': message
        }))

    @database_sync_to_async
    def check_room_participant(self):
        """Check if user is a participant of the chat room"""
        from .models import ChatRoom
        return ChatRoom.objects.filter(
            id=self.room_id,
            participants=self.user
        ).exists()

    @database_sync_to_async
    def save_message(self, content):
        """Save message to database and return message data"""
        from .models import ChatRoom, Message
        
        room = ChatRoom.objects.get(id=self.room_id)
        message = Message.objects.create(
            room=room,
            sender=self.user,
            content=content
        )
        
        # Update room's updated_at
        room.updated_at = timezone.now()
        room.save(update_fields=['updated_at'])
        
        return {
            'id': str(message.id),
            'sender_id': str(message.sender.id),
            'sender_name': message.sender.get_full_name_display(),
            'content': message.content,
            'is_mine': False,  # Will be determined client-side
            'created_at': message.created_at.isoformat(),
        }

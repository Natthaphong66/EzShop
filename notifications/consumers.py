import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time notifications"""
    
    async def connect(self):
        self.user = self.scope['user']
        
        # Check if user is authenticated
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Create user-specific group
        self.user_group_name = f'notifications_{self.user.id}'
        
        # Join user group
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send current unread count on connect
        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': unread_count
        }))
    
    async def disconnect(self, close_code):
        # Leave user group
        await self.channel_layer.group_discard(
            self.user_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming messages from WebSocket"""
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'get_notifications':
            # Send latest notifications
            notifications = await self.get_latest_notifications()
            await self.send(text_data=json.dumps({
                'type': 'notifications',
                'notifications': notifications
            }))
    
    async def notification_created(self, event):
        """Send notification to WebSocket when new notification is created"""
        notification = event['notification']
        unread_count = await self.get_unread_count()
        
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            'notification': notification,
            'unread_count': unread_count
        }))
    
    async def notification_read(self, event):
        """Update when notification is marked as read"""
        unread_count = await self.get_unread_count()
        
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': unread_count
        }))
    
    @database_sync_to_async
    def get_unread_count(self):
        """Get unread notification count"""
        from .models import Notification
        return Notification.get_unread_count(self.user)
    
    @database_sync_to_async
    def get_latest_notifications(self, limit=10):
        """Get latest notifications"""
        from .models import Notification
        from django.utils import timezone
        from datetime import timedelta
        
        notifications = Notification.objects.filter(
            user=self.user
        ).order_by('-created_at')[:limit]
        
        return [
            {
                'id': str(n.id),
                'type': n.notification_type,
                'title': n.title,
                'message': n.message[:100] + '...' if len(n.message) > 100 else n.message,
                'link': n.link,
                'is_read': n.is_read,
                'created_at': n.created_at.strftime('%d/%m/%Y %H:%M'),
                'time_ago': self.get_time_ago(n.created_at),
            }
            for n in notifications
        ]
    
    def get_time_ago(self, dt):
        """Calculate time ago"""
        from django.utils import timezone
        diff = timezone.now() - dt
        
        if diff.days > 0:
            if diff.days == 1:
                return 'เมื่อวาน'
            return f'{diff.days} วันที่แล้ว'
        
        hours = diff.seconds // 3600
        if hours > 0:
            return f'{hours} ชั่วโมงที่แล้ว'
        
        minutes = diff.seconds // 60
        if minutes > 0:
            return f'{minutes} นาทีที่แล้ว'
        
        return 'เมื่อสักครู่'


import uuid
from django.db import models
from django.conf import settings


class ChatRoom(models.Model):
    """ห้องแชทระหว่าง 2 ผู้ใช้ (buyer-seller)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name='chat_rooms'
    )
    # Optional: Link to product or auction that started the chat
    product = models.ForeignKey(
        'products.Product', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='chat_rooms'
    )
    auction = models.ForeignKey(
        'auctions.Auction', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='chat_rooms'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        participant_names = ', '.join([p.get_full_name_display() for p in self.participants.all()[:2]])
        return f"Chat: {participant_names}"

    def get_other_participant(self, user):
        """Get the other participant in the chat room"""
        return self.participants.exclude(id=user.id).first()

    def get_last_message(self):
        """Get the most recent message in the chat room"""
        return self.messages.order_by('-created_at').first()

    def get_unread_count(self, user):
        """Get count of unread messages for a user"""
        return self.messages.filter(is_read=False).exclude(sender=user).count()


class Message(models.Model):
    """ข้อความใน chat room"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        ChatRoom, 
        on_delete=models.CASCADE, 
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='sent_messages'
    )
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['room', 'created_at']),
            models.Index(fields=['sender']),
            models.Index(fields=['is_read']),
        ]

    def __str__(self):
        return f"{self.sender}: {self.content[:50]}"

    def mark_as_read(self):
        """Mark message as read"""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])

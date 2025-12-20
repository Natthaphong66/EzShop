import uuid
from django.db import models
from django.conf import settings


class Notification(models.Model):
    """การแจ้งเตือนสำหรับผู้ใช้"""
    
    class NotificationType(models.TextChoices):
        AUCTION_WON = 'auction_won', 'ชนะการประมูล'
        AUCTION_OUTBID = 'auction_outbid', 'ถูกบิดแซง'
        AUCTION_ENDING = 'auction_ending', 'ประมูลใกล้จบ'
        ORDER_CREATED = 'order_created', 'มีคำสั่งซื้อใหม่'
        ORDER_PAID = 'order_paid', 'ได้รับการชำระเงิน'
        ORDER_SHIPPED = 'order_shipped', 'สินค้าถูกจัดส่ง'
        NEW_MESSAGE = 'new_message', 'มีข้อความใหม่'
        SYSTEM = 'system', 'แจ้งเตือนจากระบบ'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Link to related objects (optional)
    link = models.CharField(max_length=500, blank=True)
    
    # Related objects for easy querying
    auction = models.ForeignKey(
        'auctions.Auction',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.title}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])
    
    @classmethod
    def create_notification(cls, user, notification_type, title, message, link='', auction=None, order=None):
        """Helper method to create a notification"""
        return cls.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
            auction=auction,
            order=order
        )
    
    @classmethod
    def get_unread_count(cls, user):
        """Get count of unread notifications for a user"""
        return cls.objects.filter(user=user, is_read=False).count()

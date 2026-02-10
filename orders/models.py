import uuid

from django.conf import settings
from django.db import models


class Order(models.Model):
    """Order model for escrow-style payment flow."""
    
    # Carrier slug mapping for tracking
    CARRIER_CHOICES = [
        ('thailand-post', 'ไปรษณีย์ไทย (Thailand Post)'),
        ('kerry-express-thailand', 'KEX Express'),
        ('flash-express', 'Flash Express'),
        ('ninjavan-thailand', 'Ninja Van'),
        ('dhl', 'DHL'),
        ('shopee-express-thailand', 'Shopee Express'),
        ('jtexpress-th', 'J&T Express'),
        ('best-express', 'Best Express'),
        ('other', 'อื่นๆ'),
    ]
    
    class Status(models.TextChoices):
        PENDING_PAYMENT = 'pending_payment', 'รอการชำระเงิน'
        ESCROW_HELD = 'escrow_held', 'เงินอยู่ในระบบ'
        SHIPPED = 'shipped', 'จัดส่งแล้ว'
        COMPLETED = 'completed', 'สำเร็จ'
        DISPUTED = 'disputed', 'มีข้อพิพาท'
        CANCELLED = 'cancelled', 'ยกเลิกแล้ว'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Stripe payment fields
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True, help_text="Stripe Payment Intent ID")
    stripe_payment_status = models.CharField(max_length=50, blank=True, null=True, help_text="Stripe payment status")
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='orders',
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='sales',
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_PAYMENT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Shipping information
    tracking_number = models.CharField(max_length=100, blank=True, null=True, verbose_name='เลขพัสดุ')
    shipping_carrier = models.CharField(max_length=100, blank=True, null=True, verbose_name='บริษัทขนส่ง')
    carrier_slug = models.CharField(max_length=50, blank=True, null=True, verbose_name='Carrier Slug', choices=CARRIER_CHOICES)
    shipped_at = models.DateTimeField(blank=True, null=True, verbose_name='วันที่จัดส่ง')
    tracking_delivered_at = models.DateTimeField(blank=True, null=True, verbose_name='วันที่จัดส่งถึง (จาก webhook)')
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['buyer']),
            models.Index(fields=['seller']),
            models.Index(fields=['status']),
            models.Index(fields=['stripe_payment_intent_id']),
            models.Index(fields=['tracking_number']),
        ]
    
    def __str__(self):
        product_name = self.product.name if self.product else '(สินค้าถูกลบ)'
        return f"Order {self.id} - {product_name}"


class TrackingEvent(models.Model):
    """
    Model to store tracking events received from 17TRACK webhooks.
    
    This model serves two purposes:
    1. Idempotency: Prevent duplicate processing using dedupe_key
    2. History: Keep a log of all tracking updates for an order
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='tracking_events',
        null=True,
        blank=True,
        help_text="The order this event belongs to (null if order not found)"
    )
    tracking_number = models.CharField(max_length=100, verbose_name='เลขพัสดุ')
    event_type = models.CharField(max_length=50, verbose_name='ประเภท event', help_text="e.g., TRACKING_UPDATED, TRACKING_STOPPED")
    status_code = models.IntegerField(default=0, verbose_name='รหัสสถานะ')
    substatus_code = models.IntegerField(default=0, verbose_name='รหัสสถานะย่อย')
    status_tag = models.CharField(max_length=50, blank=True, verbose_name='สถานะ', help_text="e.g., InTransit, Delivered")
    raw_data = models.JSONField(default=dict, verbose_name='ข้อมูลดิบจาก webhook')
    dedupe_key = models.CharField(max_length=255, unique=True, verbose_name='Dedupe Key', help_text="tracking_number|last_update_at|status|substatus")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Tracking Event'
        verbose_name_plural = 'Tracking Events'
        indexes = [
            models.Index(fields=['tracking_number']),
            models.Index(fields=['order']),
            models.Index(fields=['dedupe_key']),
        ]
    
    def __str__(self):
        return f"{self.tracking_number} - {self.event_type} - {self.status_tag}"


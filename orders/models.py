import uuid

from django.conf import settings
from django.db import models


class Order(models.Model):
    """Order model for escrow-style payment flow."""
    
    class Status(models.TextChoices):
        PENDING_PAYMENT = 'pending_payment', 'รอการชำระเงิน'
        WAITING_SOFT_VERIFY = 'waiting_soft_verify', 'รอตรวจสอบสลิป'
        ESCROW_HELD = 'escrow_held', 'เงินอยู่ในระบบ'
        SHIPPED = 'shipped', 'จัดส่งแล้ว'
        COMPLETED = 'completed', 'สำเร็จ'
        DISPUTED = 'disputed', 'มีข้อพิพาท'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
        on_delete=models.PROTECT,
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
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['buyer']),
            models.Index(fields=['seller']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Order {self.id} - {self.product.name}"

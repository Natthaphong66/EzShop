from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class Review(models.Model):
    """Model สำหรับเก็บรีวิวของผู้ขาย"""
    
    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='review',
        verbose_name='คำสั่งซื้อ'
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews_given',
        verbose_name='ผู้รีวิว'
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews_received',
        verbose_name='ผู้ขาย'
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.SET_NULL,
        null=True,
        related_name='reviews',
        verbose_name='สินค้า'
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='คะแนน'
    )
    comment = models.TextField(
        blank=True,
        verbose_name='ความคิดเห็น'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='วันที่รีวิว')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'รีวิว'
        verbose_name_plural = 'รีวิว'
    
    def __str__(self):
        return f"รีวิวจาก {self.reviewer.get_full_name_display()} - {self.rating} ดาว"

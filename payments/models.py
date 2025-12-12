import uuid

from django.db import models


class PaymentSlip(models.Model):
    """Payment slip for bank transfer verification."""
    
    class VerifyStatus(models.TextChoices):
        UNVERIFIED = 'unverified', 'ยังไม่ตรวจสอบ'
        PASSED = 'passed', 'ผ่านการตรวจสอบ'
        MISMATCH = 'mismatch', 'ข้อมูลไม่ตรงกัน'
        ERROR = 'error', 'เกิดข้อผิดพลาด'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='payment_slip',
    )
    image = models.ImageField(upload_to='payment_slips/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Verification fields
    verify_status = models.CharField(
        max_length=15,
        choices=VerifyStatus.choices,
        default=VerifyStatus.UNVERIFIED,
    )
    verify_message = models.TextField(blank=True)
    
    # OCR extracted data
    ocr_raw_text = models.TextField(blank=True)
    ocr_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    ocr_account = models.CharField(max_length=50, blank=True)
    ocr_datetime = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"PaymentSlip for Order {self.order_id}"

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
    seller_wallet_credited = models.BooleanField(
        default=False,
        help_text='ระบุว่าออเดอร์นี้ถูกเครดิตเข้าวอลเล็ทผู้ขายแล้วหรือยัง',
    )
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
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['buyer']),
            models.Index(fields=['seller']),
            models.Index(fields=['status']),
            models.Index(fields=['seller_wallet_credited']),
            models.Index(fields=['stripe_payment_intent_id']),
            models.Index(fields=['tracking_number']),
        ]
    
    def __str__(self):
        product_name = self.product.name if self.product else '(สินค้าถูกลบ)'
        return f"Order {self.id} - {product_name}"


class DisputeCase(models.Model):
    """เคสข้อพิพาทสำหรับออเดอร์ที่มีปัญหา"""

    class Reason(models.TextChoices):
        WRONG_ITEM = 'wrong_item', 'สินค้าไม่ตรงตามที่สั่ง'
        DAMAGED = 'damaged', 'สินค้าชำรุด/เสียหาย'
        NOT_RECEIVED = 'not_received', 'ไม่ได้รับสินค้า'
        INCOMPLETE = 'incomplete', 'สินค้าไม่ครบ'
        OTHER = 'other', 'อื่นๆ'

    class Status(models.TextChoices):
        OPEN = 'open', 'เปิดเคส'
        UNDER_REVIEW = 'under_review', 'กำลังตรวจสอบ'
        RESOLVED_REFUND = 'resolved_refund', 'คืนเงินแล้ว'
        RESOLVED_PARTIAL = 'resolved_partial', 'คืนเงินบางส่วน'
        RESOLVED_REJECTED = 'resolved_rejected', 'ปฏิเสธการคืนเงิน'

    BANK_CHOICES = [
        ('kbank', 'ธนาคารกสิกรไทย'),
        ('scb', 'ธนาคารไทยพาณิชย์'),
        ('bbl', 'ธนาคารกรุงเทพ'),
        ('ktb', 'ธนาคารกรุงไทย'),
        ('tmb', 'ธนาคารทหารไทยธนชาต (TTB)'),
        ('gsb', 'ธนาคารออมสิน'),
        ('bay', 'ธนาคารกรุงศรีอยุธยา'),
        ('promptpay', 'พร้อมเพย์'),
        ('other', 'อื่นๆ'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='dispute')
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='disputes_filed')

    # รายละเอียดปัญหา
    reason = models.CharField(max_length=30, choices=Reason.choices, verbose_name='สาเหตุ')
    description = models.TextField(verbose_name='รายละเอียดปัญหา')
    evidence_1 = models.ImageField(upload_to='disputes/', blank=True, null=True, verbose_name='หลักฐาน 1')
    evidence_2 = models.ImageField(upload_to='disputes/', blank=True, null=True, verbose_name='หลักฐาน 2')
    evidence_3 = models.ImageField(upload_to='disputes/', blank=True, null=True, verbose_name='หลักฐาน 3')

    # ข้อมูลบัญชีรับเงินคืน
    bank_name = models.CharField(max_length=30, choices=BANK_CHOICES, verbose_name='ธนาคาร')
    bank_account_number = models.CharField(max_length=30, verbose_name='เลขบัญชี')
    bank_account_name = models.CharField(max_length=100, verbose_name='ชื่อบัญชี')

    # สถานะเคส
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.OPEN, verbose_name='สถานะเคส')
    admin_note = models.TextField(blank=True, verbose_name='หมายเหตุแอดมิน')
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='จำนวนเงินคืน')
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='disputes_resolved', verbose_name='ผู้ตัดสิน'
    )
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='วันที่ตัดสิน')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'เคสข้อพิพาท'
        verbose_name_plural = 'เคสข้อพิพาท'

    def __str__(self):
        return f"Dispute #{str(self.id)[:8]} - {self.get_reason_display()}"




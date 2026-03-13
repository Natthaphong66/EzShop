import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models


class Wallet(models.Model):
    seller = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wallet',
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    locked_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Wallet({self.seller.phone})"

    @property
    def available_balance(self):
        return self.balance


class SellerBankAccount(models.Model):
    class BankChoices(models.TextChoices):
        KBANK = 'kbank', 'ธนาคารกสิกรไทย'
        SCB = 'scb', 'ธนาคารไทยพาณิชย์'
        BBL = 'bbl', 'ธนาคารกรุงเทพ'
        KTB = 'ktb', 'ธนาคารกรุงไทย'
        TTB = 'ttb', 'ธนาคารทหารไทยธนชาต (TTB)'
        GSB = 'gsb', 'ธนาคารออมสิน'
        BAY = 'bay', 'ธนาคารกรุงศรีอยุธยา'
        PROMPTPAY = 'promptpay', 'พร้อมเพย์'
        OTHER = 'other', 'อื่นๆ'

    seller = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bank_account',
    )
    bank_name = models.CharField(max_length=20, choices=BankChoices.choices)
    account_number = models.CharField(max_length=30)
    account_name = models.CharField(max_length=100)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.get_bank_name_display()} - {self.account_number}"


class WithdrawalRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'รอดำเนินการ'
        COMPLETED = 'completed', 'โอนแล้ว'
        REJECTED = 'rejected', 'ปฏิเสธ/ยกเลิก'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='withdrawal_requests',
    )
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.PROTECT,
        related_name='withdrawals',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    bank_name = models.CharField(max_length=20, choices=SellerBankAccount.BankChoices.choices)
    bank_account_number = models.CharField(max_length=30)
    bank_account_name = models.CharField(max_length=100)

    note = models.TextField(blank=True)
    admin_note = models.TextField(blank=True)
    transfer_slip = models.ImageField(upload_to='withdrawal_slips/', blank=True, null=True)

    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='withdrawals_processed',
    )
    processed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['seller']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Withdrawal({self.seller.phone} - {self.amount} - {self.status})"

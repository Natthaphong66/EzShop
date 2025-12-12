from django.contrib import admin
from .models import PaymentSlip


@admin.register(PaymentSlip)
class PaymentSlipAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'verify_status', 'ocr_amount', 'uploaded_at']
    list_filter = ['verify_status', 'uploaded_at']
    search_fields = ['order__id', 'ocr_account']
    readonly_fields = ['id', 'uploaded_at', 'ocr_raw_text', 'ocr_amount', 'ocr_account', 'ocr_datetime']
    raw_id_fields = ['order']
    ordering = ['-uploaded_at']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('id', 'order', 'image', 'uploaded_at')
        }),
        ('Verification', {
            'fields': ('verify_status', 'verify_message')
        }),
        ('OCR Data', {
            'fields': ('ocr_raw_text', 'ocr_amount', 'ocr_account', 'ocr_datetime'),
            'classes': ('collapse',)
        }),
    )

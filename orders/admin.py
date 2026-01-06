from django.contrib import admin
from .models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'buyer', 'seller', 'product', 'amount', 'status', 'tracking_number', 'created_at']
    list_filter = ['status', 'created_at', 'shipping_carrier']
    search_fields = ['buyer__email', 'seller__email', 'product__name', 'tracking_number']
    readonly_fields = ['id', 'created_at', 'updated_at', 'shipped_at']
    raw_id_fields = ['buyer', 'seller', 'product']
    ordering = ['-created_at']
    fieldsets = (
        ('ข้อมูลคำสั่งซื้อ', {
            'fields': ('id', 'buyer', 'seller', 'product', 'amount', 'status')
        }),
        ('ข้อมูลการชำระเงิน', {
            'fields': ('stripe_payment_intent_id', 'stripe_payment_status')
        }),
        ('ข้อมูลการจัดส่ง', {
            'fields': ('tracking_number', 'shipping_carrier', 'shipped_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

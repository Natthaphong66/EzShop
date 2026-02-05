from django.contrib import admin
from .models import Order, TrackingEvent


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'buyer', 'seller', 'product', 'amount', 'status', 'tracking_number', 'created_at']
    list_filter = ['status', 'created_at', 'shipping_carrier']
    search_fields = ['buyer__email', 'seller__email', 'product__name', 'tracking_number']
    readonly_fields = ['id', 'created_at', 'updated_at', 'shipped_at', 'tracking_delivered_at']
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
            'fields': ('tracking_number', 'shipping_carrier', 'carrier_slug', 'shipped_at', 'tracking_delivered_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TrackingEvent)
class TrackingEventAdmin(admin.ModelAdmin):
    list_display = ['id', 'tracking_number', 'event_type', 'status_tag', 'status_code', 'created_at']
    list_filter = ['event_type', 'status_tag', 'created_at']
    search_fields = ['tracking_number', 'order__id', 'dedupe_key']
    readonly_fields = ['id', 'created_at', 'raw_data', 'dedupe_key']
    raw_id_fields = ['order']
    ordering = ['-created_at']
    fieldsets = (
        ('Event Info', {
            'fields': ('id', 'tracking_number', 'event_type', 'order')
        }),
        ('Status', {
            'fields': ('status_code', 'substatus_code', 'status_tag')
        }),
        ('Raw Data', {
            'fields': ('raw_data', 'dedupe_key'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

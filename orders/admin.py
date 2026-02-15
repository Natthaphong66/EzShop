from django.contrib import admin
from django.utils import timezone
from .models import Order, TrackingEvent, DisputeCase


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


@admin.register(DisputeCase)
class DisputeCaseAdmin(admin.ModelAdmin):
    list_display = ['short_id', 'order_link', 'buyer', 'reason_display', 'status_badge', 'bank_name_display', 'created_at']
    list_filter = ['status', 'reason', 'bank_name', 'created_at']
    search_fields = ['order__id', 'buyer__email', 'buyer__phone_number', 'description', 'bank_account_number']
    readonly_fields = [
        'id', 'order', 'buyer', 'reason', 'description',
        'evidence_1', 'evidence_2', 'evidence_3',
        'bank_name', 'bank_account_number', 'bank_account_name',
        'created_at', 'updated_at',
    ]
    raw_id_fields = ['resolved_by']
    ordering = ['-created_at']
    actions = ['mark_under_review', 'approve_full_refund', 'reject_dispute']

    fieldsets = (
        ('ข้อมูลคำสั่งซื้อ', {
            'fields': ('id', 'order', 'buyer'),
        }),
        ('รายละเอียดปัญหา', {
            'fields': ('reason', 'description', 'evidence_1', 'evidence_2', 'evidence_3'),
        }),
        ('ข้อมูลบัญชีรับเงินคืน', {
            'fields': ('bank_name', 'bank_account_number', 'bank_account_name'),
        }),
        ('การตัดสินเคส', {
            'fields': ('status', 'refund_amount', 'admin_note', 'resolved_by', 'resolved_at'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def short_id(self, obj):
        return str(obj.id)[:8]
    short_id.short_description = 'ID'

    def order_link(self, obj):
        from django.utils.html import format_html
        return format_html(
            '<a href="/admin/orders/order/{}/change/">{}</a>',
            obj.order_id, str(obj.order_id)[:8]
        )
    order_link.short_description = 'Order'

    def reason_display(self, obj):
        return obj.get_reason_display()
    reason_display.short_description = 'สาเหตุ'

    def bank_name_display(self, obj):
        return obj.get_bank_name_display()
    bank_name_display.short_description = 'ธนาคาร'

    def status_badge(self, obj):
        from django.utils.html import format_html
        colors = {
            'open': '#f59e0b',
            'under_review': '#3b82f6',
            'resolved_refund': '#10b981',
            'resolved_partial': '#8b5cf6',
            'resolved_rejected': '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'สถานะ'

    @admin.action(description='เปลี่ยนสถานะเป็น "กำลังตรวจสอบ"')
    def mark_under_review(self, request, queryset):
        updated = queryset.filter(status=DisputeCase.Status.OPEN).update(status=DisputeCase.Status.UNDER_REVIEW)
        self.message_user(request, f'อัปเดต {updated} เคสเป็น "กำลังตรวจสอบ"')

    @admin.action(description='อนุมัติคืนเงินเต็มจำนวน')
    def approve_full_refund(self, request, queryset):
        count = 0
        for dispute in queryset.filter(status__in=[DisputeCase.Status.OPEN, DisputeCase.Status.UNDER_REVIEW]):
            dispute.status = DisputeCase.Status.RESOLVED_REFUND
            dispute.refund_amount = dispute.order.amount
            dispute.resolved_by = request.user
            dispute.resolved_at = timezone.now()
            dispute.save()
            count += 1

            try:
                from notifications.services import notify_system
                notify_system(
                    user=dispute.buyer,
                    title='เคสข้อพิพาทได้รับการอนุมัติ',
                    message=f'คำสั่งซื้อ "{dispute.order.product.name}" ได้รับการอนุมัติคืนเงินเต็มจำนวน ฿{dispute.order.amount:,.0f}',
                    link=f'/orders/{dispute.order.id}/'
                )
            except Exception:
                pass

        self.message_user(request, f'อนุมัติคืนเงิน {count} เคส')

    @admin.action(description='ปฏิเสธการคืนเงิน')
    def reject_dispute(self, request, queryset):
        count = 0
        for dispute in queryset.filter(status__in=[DisputeCase.Status.OPEN, DisputeCase.Status.UNDER_REVIEW]):
            dispute.status = DisputeCase.Status.RESOLVED_REJECTED
            dispute.resolved_by = request.user
            dispute.resolved_at = timezone.now()
            dispute.save()
            count += 1

            try:
                from notifications.services import notify_system
                notify_system(
                    user=dispute.buyer,
                    title='เคสข้อพิพาทถูกปฏิเสธ',
                    message=f'คำสั่งซื้อ "{dispute.order.product.name}" ไม่ผ่านการอนุมัติคืนเงิน',
                    link=f'/orders/{dispute.order.id}/'
                )
            except Exception:
                pass

        self.message_user(request, f'ปฏิเสธ {count} เคส')


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

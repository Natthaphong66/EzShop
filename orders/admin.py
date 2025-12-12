from django.contrib import admin
from .models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'buyer', 'seller', 'product', 'amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['buyer__email', 'seller__email', 'product__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['buyer', 'seller', 'product']
    ordering = ['-created_at']

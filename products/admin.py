from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "seller", "price", "condition", "created_at")
    list_filter = ("condition", "created_at")
    search_fields = ("name", "seller__email")


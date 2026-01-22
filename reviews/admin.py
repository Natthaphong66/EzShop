from django.contrib import admin
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['reviewer', 'seller', 'product', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['reviewer__email', 'seller__email', 'comment']
    readonly_fields = ['order', 'reviewer', 'seller', 'product', 'created_at']

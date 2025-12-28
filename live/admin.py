from django.contrib import admin
from .models import LiveStream


@admin.register(LiveStream)
class LiveStreamAdmin(admin.ModelAdmin):
    list_display = ['title', 'host', 'status', 'started_at', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'host__first_name', 'host__last_name', 'channel_name']
    readonly_fields = ['id', 'channel_name', 'created_at', 'updated_at']

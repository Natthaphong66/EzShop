from django.contrib import admin
from .models import ChatRoom, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ['id', 'sender', 'content', 'is_read', 'created_at']
    can_delete = False


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_participants', 'product', 'auction', 'created_at', 'updated_at']
    list_filter = ['created_at']
    search_fields = ['participants__email', 'participants__phone']
    readonly_fields = ['id', 'created_at', 'updated_at']
    inlines = [MessageInline]

    def get_participants(self, obj):
        return ', '.join([p.get_full_name_display() for p in obj.participants.all()])
    get_participants.short_description = 'Participants'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'room', 'sender', 'content_preview', 'is_read', 'created_at']
    list_filter = ['is_read', 'created_at']
    search_fields = ['content', 'sender__email', 'sender__phone']
    readonly_fields = ['id', 'created_at']

    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'

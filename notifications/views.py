from django.views.generic import ListView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from .models import Notification


class NotificationListView(LoginRequiredMixin, ListView):
    """แสดงรายการแจ้งเตือนทั้งหมด"""
    model = Notification
    template_name = 'notifications/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['unread_count'] = Notification.get_unread_count(self.request.user)
        return context


class NotificationDropdownView(LoginRequiredMixin, View):
    """API สำหรับดึง notifications ล่าสุด (AJAX)"""
    
    def get(self, request):
        notifications = Notification.objects.filter(
            user=request.user
        ).order_by('-created_at')[:10]
        
        data = {
            'unread_count': Notification.get_unread_count(request.user),
            'notifications': [
                {
                    'id': str(n.id),
                    'type': n.notification_type,
                    'title': n.title,
                    'message': n.message[:100] + '...' if len(n.message) > 100 else n.message,
                    'link': n.link,
                    'is_read': n.is_read,
                    'created_at': n.created_at.strftime('%d/%m/%Y %H:%M'),
                    'time_ago': self.get_time_ago(n.created_at),
                }
                for n in notifications
            ]
        }
        return JsonResponse(data)
    
    def get_time_ago(self, dt):
        """คำนวณเวลาที่ผ่านมา"""
        from django.utils import timezone
        diff = timezone.now() - dt
        
        if diff.days > 0:
            if diff.days == 1:
                return 'เมื่อวาน'
            return f'{diff.days} วันที่แล้ว'
        
        hours = diff.seconds // 3600
        if hours > 0:
            return f'{hours} ชั่วโมงที่แล้ว'
        
        minutes = diff.seconds // 60
        if minutes > 0:
            return f'{minutes} นาทีที่แล้ว'
        
        return 'เมื่อสักครู่'


class MarkAsReadView(LoginRequiredMixin, View):
    """Mark notification as read (AJAX)"""
    
    def post(self, request, notification_id):
        notification = get_object_or_404(
            Notification,
            id=notification_id,
            user=request.user
        )
        notification.mark_as_read()
        
        # Send WebSocket update
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f'notifications_{request.user.id}',
                    {
                        'type': 'notification_read',
                    }
                )
        except Exception as e:
            print(f"Failed to send WebSocket update: {e}")
        
        return JsonResponse({'success': True})


class MarkAllAsReadView(LoginRequiredMixin, View):
    """Mark all notifications as read (AJAX)"""
    
    def post(self, request):
        updated = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True)
        
        # Send WebSocket update
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f'notifications_{request.user.id}',
                    {
                        'type': 'notification_read',
                    }
                )
        except Exception as e:
            print(f"Failed to send WebSocket update: {e}")
        
        return JsonResponse({'success': True, 'marked_count': updated})

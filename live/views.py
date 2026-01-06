from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
import uuid
import json

from .models import LiveStream
from .agora_utils import generate_agora_token


class LiveStreamListView(ListView):
    """แสดงรายการ live streams ทั้งหมด"""
    model = LiveStream
    template_name = 'live/stream_list.html'
    context_object_name = 'streams'
    paginate_by = 20
    
    def get_queryset(self):
        return LiveStream.objects.filter(
            status=LiveStream.Status.LIVE
        ).select_related('host').order_by('-started_at')


class LiveStreamDetailView(DetailView):
    """ดู live stream"""
    model = LiveStream
    template_name = 'live/stream_detail.html'
    context_object_name = 'stream'
    
    def get_context_data(self, **kwargs):
        try:
            context = super().get_context_data(**kwargs)
            # Pass Agora credentials
            app_id = getattr(settings, 'AGORA_APP_ID', None)
            app_certificate = getattr(settings, 'AGORA_APP_CERTIFICATE', None)
            context['agora_app_id'] = app_id if app_id else None
            context['agora_app_certificate'] = app_certificate if app_certificate else None
            
            return context
        except Exception as e:
            # If there's any error, still return basic context
            context = super().get_context_data(**kwargs)
            context['agora_app_id'] = None
            context['agora_app_certificate'] = None
            print(f"Error in get_context_data: {e}")
            return context


class LiveStreamCreateView(LoginRequiredMixin, CreateView):
    """สร้าง live stream ใหม่"""
    model = LiveStream
    template_name = 'live/stream_form.html'
    fields = ['title', 'description']
    success_url = reverse_lazy('live:stream_list')
    
    def form_valid(self, form):
        stream = form.save(commit=False)
        stream.host = self.request.user
        # Generate unique channel name
        stream.channel_name = f"live_{uuid.uuid4().hex[:16]}"
        stream.status = LiveStream.Status.LIVE
        stream.started_at = timezone.now()
        stream.save()
        messages.success(self.request, 'เริ่มถ่ายทอดสดแล้ว!')
        return redirect('live:stream_detail', pk=stream.pk)


class LiveStreamEndView(LoginRequiredMixin, View):
    """จบ live stream"""
    
    def post(self, request, pk):
        stream = get_object_or_404(LiveStream, pk=pk, host=request.user)
        if stream.status == LiveStream.Status.LIVE:
            stream.end_stream()
            messages.success(request, 'หยุดถ่ายทอดสดแล้ว')
        return redirect('live:stream_list')




class MyLiveStreamsView(LoginRequiredMixin, ListView):
    """แสดงรายการ live streams ของผู้ใช้"""
    model = LiveStream
    template_name = 'live/my_streams.html'
    context_object_name = 'streams'
    paginate_by = 20
    
    def get_queryset(self):
        return LiveStream.objects.filter(
            host=self.request.user
        ).order_by('-created_at')


@method_decorator(ensure_csrf_cookie, name='dispatch')
class AgoraTokenView(View):
    """Generate Agora token for joining channel"""

    def post(self, request):
        try:
            data = json.loads(request.body)

            channel_name = data.get('channel_name')
            uid = data.get('uid')              # ✅ FIX ตรงนี้
            role = int(data.get('role', 1))    # 1 = publisher, 2 = subscriber

            if not channel_name:
                return JsonResponse({'error': 'channel_name is required'}, status=400)

            if not uid:
                return JsonResponse({'error': 'uid is required'}, status=400)

            token = generate_agora_token(channel_name, uid, role)

            return JsonResponse({
                'token': token,
                'uid': uid,
                'channel': channel_name,
                'app_id': settings.AGORA_APP_ID
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings
from django.utils import timezone
import uuid

from .models import LiveStream
from .agora_service import RtcTokenBuilder


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
        context = super().get_context_data(**kwargs)
        # Only pass app_id if it's set (not empty)
        app_id = settings.AGORA_APP_ID
        context['agora_app_id'] = app_id if app_id else None
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


class AgoraTokenView(LoginRequiredMixin, View):
    """Generate Agora RTC token for joining live stream"""
    
    def post(self, request, pk):
        stream = get_object_or_404(LiveStream, pk=pk)
        
        # Check if stream is live
        if stream.status != LiveStream.Status.LIVE:
            return JsonResponse({
                'error': 'Stream is not live'
            }, status=400)
        
        # Determine role: host is publisher, others are subscribers
        role = "publisher" if request.user == stream.host else "subscriber"
        
        # Generate token
        try:
            # Check if App ID is configured
            app_id = settings.AGORA_APP_ID
            app_cert = settings.AGORA_APP_CERTIFICATE
            
            # Debug logging (remove in production)
            print(f"DEBUG: AGORA_APP_ID = {app_id[:10]}..." if app_id and len(app_id) > 10 else f"DEBUG: AGORA_APP_ID = {app_id}")
            print(f"DEBUG: AGORA_APP_ID full length = {len(app_id) if app_id else 0}")
            print(f"DEBUG: AGORA_APP_CERTIFICATE = {'Set' if app_cert else 'Not set'}")
            print(f"DEBUG: Channel name = {stream.channel_name}")
            
            if not app_id or app_id.strip() == '':
                return JsonResponse({
                    'success': False,
                    'error': 'AGORA_APP_ID ไม่ได้ตั้งค่า กรุณาเพิ่มใน .env file และ restart Django server'
                }, status=400)
            
            if not app_cert or app_cert.strip() == '':
                return JsonResponse({
                    'success': False,
                    'error': 'AGORA_APP_CERTIFICATE ไม่ได้ตั้งค่า กรุณาเพิ่มใน .env file และ restart Django server'
                }, status=400)
            
            # Use numeric UID (user ID as integer)
            # Convert user ID to integer for numeric UID (max 2^31 - 1)
            uid = int(request.user.id) & 0x7FFFFFFF  # Ensure positive integer
            
            from .agora_service import RtcTokenBuilder
            import time
            expire_timestamp = int(timezone.now().timestamp()) + 3600
            
            token = RtcTokenBuilder.buildTokenWithUid(
                app_id,
                app_cert,
                stream.channel_name,
                uid,
                RtcTokenBuilder.ROLE_PUBLISHER if role == "publisher" else RtcTokenBuilder.ROLE_SUBSCRIBER,
                expire_timestamp
            )
            
            return JsonResponse({
                'success': True,
                'token': token,
                'channel_name': stream.channel_name,
                'uid': uid,
                'role': role,
                'app_id': app_id
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


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

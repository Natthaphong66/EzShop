from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class LiveStream(models.Model):
    """Live Stream model for Agora live streaming"""
    
    class Status(models.TextChoices):
        PREPARING = "preparing", "กำลังเตรียม"
        LIVE = "live", "กำลังถ่ายทอด"
        ENDED = "ended", "จบแล้ว"
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='live_streams')
    
    # Agora channel settings
    channel_name = models.CharField(max_length=255, unique=True, help_text="Agora channel name")
    
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PREPARING)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def start_stream(self):
        """Start the live stream"""
        self.status = self.Status.LIVE
        self.started_at = timezone.now()
        self.save()

    def end_stream(self):
        """End the live stream"""
        self.status = self.Status.ENDED
        self.ended_at = timezone.now()
        self.save()
    
    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"
    
    class Meta:
        ordering = ['-created_at']


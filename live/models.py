import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class LiveStream(models.Model):
    """Live Stream model for Agora live streaming"""
    
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        LIVE = 'live', 'Live'
        ENDED = 'ended', 'Ended'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='live_streams')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Agora channel settings
    channel_name = models.CharField(max_length=255, unique=True, help_text="Agora channel name")
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['host']),
            models.Index(fields=['status']),
            models.Index(fields=['channel_name']),
        ]
    
    def __str__(self):
        return f"{self.title} by {self.host.get_full_name_display()}"
    
    def start_stream(self):
        """Start the live stream"""
        if self.status == self.Status.LIVE:
            return
        self.status = self.Status.LIVE
        self.started_at = timezone.now()
        self.save()
    
    def end_stream(self):
        """End the live stream"""
        if self.status == self.Status.ENDED:
            return
        self.status = self.Status.ENDED
        self.ended_at = timezone.now()
        self.save()

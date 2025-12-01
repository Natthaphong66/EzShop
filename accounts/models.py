# accounts/models.py
import uuid
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.db import models
from .managers import UserManager


class User(AbstractUser):
    """Single profile that can act as both buyer and seller."""

    username = None
    email = models.EmailField(unique=True)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=20, unique=True)
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    is_seller = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ['email']

    def __str__(self):
        return self.phone
    
    def get_full_name_display(self):
        """คืนค่าชื่อเต็ม หรือ email ถ้าไม่มีชื่อ"""
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.email.split('@')[0]
    
    def get_membership_duration(self):
        """คำนวณระยะเวลาที่เป็นสมาชิก"""
        if not self.created_at:
            return "0 วัน"
        
        delta = timezone.now() - self.created_at
        months = delta.days // 30
        days = delta.days % 30
        
        if months > 0:
            return f"{months} เดือน {days} วัน"
        return f"{days} วัน"
    
    def get_member_id(self):
        """สร้าง Member ID จาก UUID"""
        # ใช้ 8 ตัวเลขสุดท้ายของ UUID
        return str(self.id).replace('-', '')[-8:]

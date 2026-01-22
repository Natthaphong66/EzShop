from django.urls import reverse_lazy
from django.views import generic
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import UpdateView, DeleteView
from django.contrib.auth.views import PasswordChangeView as DjangoPasswordChangeView
from django.contrib import messages
from .models import User
from .forms import CustomUserCreationForm, ProfileUpdateForm

class HomePageView(TemplateView):
    template_name = 'home.html'

# --- Auth ---

class SignUpView(generic.CreateView):
    form_class = CustomUserCreationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('accounts:login')
   

class ProfileView(LoginRequiredMixin, TemplateView):
    """หน้าโปรไฟล์หลักที่แสดงข้อมูลและแท็บ"""
    template_name = 'accounts/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['profile_user'] = user
        
        # ตรวจสอบว่ามี products app หรือไม่
        try:
            from products.models import Product
            context['products'] = Product.objects.filter(seller=user)[:10]
            context['products_count'] = Product.objects.filter(seller=user).count()
        except:
            context['products'] = []
            context['products_count'] = 0
        
        # ดึงรีวิวของผู้ใช้ (ในฐานะผู้ขาย)
        try:
            from reviews.models import Review
            from django.db.models import Avg
            reviews = Review.objects.filter(seller=user).select_related('reviewer', 'product')
            context['reviews'] = reviews
            context['reviews_count'] = reviews.count()
            
            # คำนวณคะแนนเฉลี่ย
            avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']
            context['average_rating'] = round(avg_rating, 1) if avg_rating else 0
        except:
            context['reviews'] = []
            context['reviews_count'] = 0
            context['average_rating'] = 0
        
        return context

class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = ProfileUpdateForm
    template_name = 'accounts/profile_edit.html'
    # เมื่อแก้ไขสำเร็จ ให้กลับมาที่หน้าโปรไฟล์
    success_url = reverse_lazy('accounts:profile')

    def get_object(self, queryset=None):
        # ทำให้ View นี้แก้ไขข้อมูลของ User ที่ login อยู่เสมอ
        return self.request.user
    
    def form_valid(self, form):
        messages.success(self.request, 'อัปเดตโปรไฟล์สำเร็จแล้ว')
        return super().form_valid(form)

class ProfileDeleteView(LoginRequiredMixin, DeleteView):
    model = User
    template_name = 'accounts/profile_confirm_delete.html'
    # เมื่อลบบัญชีสำเร็จ ให้กลับไปที่หน้าแรก
    success_url = reverse_lazy('home')

    def get_object(self, queryset=None):
        return self.request.user

class PasswordChangeView(LoginRequiredMixin, DjangoPasswordChangeView):
    template_name = 'registration/password_change.html'
    success_url = reverse_lazy('accounts:profile')
    
    def form_valid(self, form):
        messages.success(self.request, 'เปลี่ยนรหัสผ่านสำเร็จแล้ว')
        return super().form_valid(form)

class ManageListingsView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/manage_listings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Import models here to avoid circular imports if any
        from products.models import Product
        from auctions.models import Auction
        
        # Fetch Marketplace Products
        context['products'] = Product.objects.filter(seller=user).order_by('-created_at')
        
        # Fetch Auctions
        context['auctions'] = Auction.objects.filter(seller=user).order_by('-created_at')
        
        return context

from django.urls import reverse_lazy
from django.views import generic
from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import UpdateView, DeleteView
from django.contrib.auth.views import PasswordChangeView as DjangoPasswordChangeView
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from .models import User
from .forms import CustomUserCreationForm, ProfileUpdateForm

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
            from auctions.models import Auction
            all_products = Product.objects.filter(seller=user)
            
            # แยกสินค้า marketplace (ไม่มี auction) กับ auction (มี auction)
            auction_product_ids = Auction.objects.filter(seller=user).values_list('product_id', flat=True)
            marketplace_products = all_products.exclude(id__in=auction_product_ids)
            auction_products = all_products.filter(id__in=auction_product_ids).select_related('auction')
            
            context['products'] = all_products[:10]
            context['products_count'] = all_products.count()
            context['marketplace_products'] = marketplace_products
            context['marketplace_count'] = marketplace_products.count()
            context['auction_products'] = auction_products
            context['auction_count'] = auction_products.count()
        except:
            context['products'] = []
            context['products_count'] = 0
            context['marketplace_products'] = []
            context['marketplace_count'] = 0
            context['auction_products'] = []
            context['auction_count'] = 0
        
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


class PublicProfileView(TemplateView):
    """หน้าโปรไฟล์สาธารณะของผู้ขาย"""
    template_name = 'accounts/public_profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile_user = get_object_or_404(User, id=kwargs['user_id'])
        context['profile_user'] = profile_user

        try:
            from products.models import Product
            products = Product.objects.filter(
                seller=profile_user,
                status=Product.Status.APPROVED,
                is_sold=False,
            ).exclude(auction__isnull=False).order_by('-created_at')
            context['products'] = products[:8]
            context['products_count'] = products.count()
        except Exception:
            context['products'] = []
            context['products_count'] = 0

        try:
            from reviews.models import Review
            from django.db.models import Avg
            reviews = Review.objects.filter(seller=profile_user).select_related('reviewer', 'product').order_by('-created_at')
            context['reviews'] = reviews[:6]
            context['reviews_count'] = reviews.count()
            avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']
            context['average_rating'] = round(avg_rating, 1) if avg_rating else 0
        except Exception:
            context['reviews'] = []
            context['reviews_count'] = 0
            context['average_rating'] = 0

        return context

class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = ProfileUpdateForm
    template_name = 'accounts/profile_edit.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self, queryset=None):
        return self.request.user
    
    def form_valid(self, form):
        messages.success(self.request, 'อัปเดตโปรไฟล์สำเร็จแล้ว')
        return super().form_valid(form)

class ProfileDeleteView(LoginRequiredMixin, DeleteView):
    model = User
    template_name = 'accounts/profile_confirm_delete.html'
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
        
        from products.models import Product
        from auctions.models import Auction
        
        context['products'] = Product.objects.filter(seller=user, auction__isnull=True).order_by('-created_at')
        context['auctions'] = Auction.objects.filter(seller=user).order_by('-created_at')
        
        return context


class StaffRequiredMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.is_staff or self.request.user.is_superuser
        )

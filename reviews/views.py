from django.views.generic import CreateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.db.models import Avg

from .models import Review
from .forms import ReviewForm
from orders.models import Order


class CreateReviewView(LoginRequiredMixin, CreateView):
    """สร้างรีวิวหลังจากยืนยันรับสินค้า"""
    model = Review
    form_class = ReviewForm
    template_name = 'reviews/create_review.html'
    
    def dispatch(self, request, *args, **kwargs):
        self.order = get_object_or_404(
            Order, 
            id=kwargs['order_id'], 
            buyer=request.user,
            status=Order.Status.COMPLETED
        )
        
        # ถ้ารีวิวแล้วให้ redirect ไปหน้า order detail
        if hasattr(self.order, 'review'):
            messages.info(request, 'คุณได้รีวิวคำสั่งซื้อนี้แล้ว')
            return redirect('orders:order_detail', order_id=self.order.id)
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['order'] = self.order
        return context
    
    def form_valid(self, form):
        form.instance.order = self.order
        form.instance.reviewer = self.request.user
        form.instance.seller = self.order.seller
        form.instance.product = self.order.product
        
        messages.success(self.request, 'ขอบคุณสำหรับรีวิว!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('orders:order_detail', kwargs={'order_id': self.order.id})


class SkipReviewView(LoginRequiredMixin, View):
    """ข้ามการรีวิว"""
    
    def get(self, request, order_id):
        order = get_object_or_404(
            Order, 
            id=order_id, 
            buyer=request.user,
            status=Order.Status.COMPLETED
        )
        return redirect('orders:order_detail', order_id=order.id)

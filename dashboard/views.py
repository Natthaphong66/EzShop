from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta

from accounts.models import User
from products.models import Product
from orders.models import Order
from auctions.models import Auction, Bid
from reviews.models import Review
from live.models import LiveStream


class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Admin Dashboard แสดงสถิติและข้อมูลสรุปของระบบ"""
    template_name = 'dashboard/admin_dashboard.html'
    
    def test_func(self):
        """ตรวจสอบว่าผู้ใช้เป็น admin (is_staff หรือ is_superuser)"""
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        today = now.date()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        # ===== User Statistics =====
        context['total_users'] = User.objects.count()
        context['users_today'] = User.objects.filter(created_at__date=today).count()
        context['users_week'] = User.objects.filter(created_at__gte=week_ago).count()
        context['users_month'] = User.objects.filter(created_at__gte=month_ago).count()
        
        # ===== Product Statistics =====
        context['total_products'] = Product.objects.count()
        context['products_pending'] = Product.objects.filter(status=Product.Status.PENDING).count()
        context['products_approved'] = Product.objects.filter(status=Product.Status.APPROVED).count()
        context['products_rejected'] = Product.objects.filter(status=Product.Status.REJECTED).count()
        
        # ===== Order Statistics =====
        context['total_orders'] = Order.objects.count()
        context['orders_pending'] = Order.objects.filter(status=Order.Status.PENDING_PAYMENT).count()
        context['orders_escrow'] = Order.objects.filter(status=Order.Status.ESCROW_HELD).count()
        context['orders_shipped'] = Order.objects.filter(status=Order.Status.SHIPPED).count()
        context['orders_completed'] = Order.objects.filter(status=Order.Status.COMPLETED).count()
        context['orders_disputed'] = Order.objects.filter(status=Order.Status.DISPUTED).count()
        context['orders_cancelled'] = Order.objects.filter(status=Order.Status.CANCELLED).count()
        
        # Total revenue from completed orders
        revenue = Order.objects.filter(status=Order.Status.COMPLETED).aggregate(
            total=Sum('amount')
        )
        context['total_revenue'] = revenue['total'] or 0
        
        # Revenue this month
        monthly_revenue = Order.objects.filter(
            status=Order.Status.COMPLETED,
            created_at__gte=month_ago
        ).aggregate(total=Sum('amount'))
        context['monthly_revenue'] = monthly_revenue['total'] or 0
        
        # ===== Auction Statistics =====
        context['auctions_live'] = Auction.objects.filter(status=Auction.Status.LIVE).count()
        context['auctions_ended'] = Auction.objects.filter(status=Auction.Status.ENDED).count()
        context['total_bids'] = Bid.objects.count()
        
        # ===== Review Statistics =====
        context['total_reviews'] = Review.objects.count()
        avg_rating = Review.objects.aggregate(avg=Avg('rating'))
        context['avg_rating'] = round(avg_rating['avg'] or 0, 1)
        
        # ===== Live Stream Statistics =====
        context['streams_live'] = LiveStream.objects.filter(status=LiveStream.Status.LIVE).count()
        context['total_streams'] = LiveStream.objects.count()
        
        # ===== Recent Data =====
        context['recent_orders'] = Order.objects.select_related(
            'buyer', 'seller', 'product'
        ).order_by('-created_at')[:5]
        
        context['pending_products'] = Product.objects.filter(
            status=Product.Status.PENDING
        ).select_related('seller').order_by('-created_at')[:5]
        
        context['recent_reviews'] = Review.objects.select_related(
            'reviewer', 'seller', 'product'
        ).order_by('-created_at')[:5]
        
        return context

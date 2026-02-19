from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Sum, Avg
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta

from accounts.models import User
from products.models import Product
from orders.models import Order, DisputeCase
from auctions.models import Auction, Bid
from reviews.models import Review
from live.models import LiveStream


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser


class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Admin Dashboard แสดงสถิติและข้อมูลสรุปของระบบ"""
    template_name = 'dashboard/admin_dashboard.html'
    
    def test_func(self):
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
        
        # ===== Dispute Statistics =====
        context['disputes_open'] = DisputeCase.objects.filter(
            status__in=[DisputeCase.Status.OPEN, DisputeCase.Status.UNDER_REVIEW]
        ).count()
        
        return context


class DisputeListView(StaffRequiredMixin, TemplateView):
    """หน้าจัดการข้อพิพาท"""
    template_name = 'dashboard/dispute_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        status_filter = self.request.GET.get('status', 'open')

        qs = DisputeCase.objects.select_related('order', 'order__product', 'order__seller', 'buyer')

        if status_filter == 'all':
            disputes = qs
        elif status_filter == 'resolved':
            disputes = qs.filter(status__in=[
                DisputeCase.Status.RESOLVED_REFUND,
                DisputeCase.Status.RESOLVED_PARTIAL,
                DisputeCase.Status.RESOLVED_REJECTED,
            ])
        else:
            disputes = qs.filter(status=status_filter)

        context['disputes'] = disputes.order_by('-created_at')
        context['status_filter'] = status_filter

        context['count_open'] = DisputeCase.objects.filter(status=DisputeCase.Status.OPEN).count()
        context['count_review'] = DisputeCase.objects.filter(status=DisputeCase.Status.UNDER_REVIEW).count()
        context['count_resolved'] = DisputeCase.objects.filter(status__in=[
            DisputeCase.Status.RESOLVED_REFUND,
            DisputeCase.Status.RESOLVED_PARTIAL,
            DisputeCase.Status.RESOLVED_REJECTED,
        ]).count()
        context['count_all'] = DisputeCase.objects.count()

        return context


class DisputeDetailView(StaffRequiredMixin, TemplateView):
    """หน้ารายละเอียดเคสข้อพิพาท"""
    template_name = 'dashboard/dispute_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dispute = get_object_or_404(
            DisputeCase.objects.select_related(
                'order', 'order__product', 'order__seller', 'order__buyer',
                'buyer', 'resolved_by'
            ),
            id=kwargs['dispute_id']
        )
        context['dispute'] = dispute
        context['order'] = dispute.order
        return context


class DisputeActionView(StaffRequiredMixin, View):
    """ดำเนินการกับเคสข้อพิพาท"""

    def post(self, request, dispute_id):
        dispute = get_object_or_404(DisputeCase, id=dispute_id)
        action = request.POST.get('action')

        if action == 'under_review':
            dispute.status = DisputeCase.Status.UNDER_REVIEW
            dispute.save(update_fields=['status', 'updated_at'])
            messages.success(request, 'เปลี่ยนสถานะเป็น "กำลังตรวจสอบ" แล้ว')

        elif action == 'refund':
            dispute.status = DisputeCase.Status.RESOLVED_REFUND
            dispute.refund_amount = dispute.order.amount
            dispute.admin_note = request.POST.get('admin_note', '').strip()
            dispute.resolved_by = request.user
            dispute.resolved_at = timezone.now()
            dispute.save(update_fields=[
                'status', 'refund_amount', 'admin_note',
                'resolved_by', 'resolved_at', 'updated_at'
            ])

            dispute.order.status = Order.Status.CANCELLED
            dispute.order.save(update_fields=['status', 'updated_at'])

            try:
                from notifications.services import notify_system
                notify_system(
                    user=dispute.buyer,
                    title='อนุมัติคืนเงินแล้ว',
                    message=f'คำสั่งซื้อ "{dispute.order.product.name}" ได้รับการอนุมัติคืนเงิน ฿{dispute.order.amount:,.0f}',
                    link=f'/orders/{dispute.order.id}/'
                )
            except Exception:
                pass
            messages.success(request, 'อนุมัติคืนเงินเต็มจำนวนเรียบร้อย')

        elif action == 'partial_refund':
            refund_amount = request.POST.get('refund_amount', '').strip()
            if not refund_amount:
                messages.error(request, 'กรุณาระบุจำนวนเงินคืน')
                return redirect('dashboard:dispute_detail', dispute_id=dispute_id)
            try:
                refund_amount = round(float(refund_amount), 2)
            except ValueError:
                messages.error(request, 'จำนวนเงินไม่ถูกต้อง')
                return redirect('dashboard:dispute_detail', dispute_id=dispute_id)

            if refund_amount <= 0 or refund_amount > float(dispute.order.amount):
                messages.error(request, 'จำนวนเงินคืนต้องมากกว่า 0 และไม่เกินยอดคำสั่งซื้อ')
                return redirect('dashboard:dispute_detail', dispute_id=dispute_id)

            dispute.status = DisputeCase.Status.RESOLVED_PARTIAL
            dispute.refund_amount = refund_amount
            dispute.admin_note = request.POST.get('admin_note', '').strip()
            dispute.resolved_by = request.user
            dispute.resolved_at = timezone.now()
            dispute.save(update_fields=[
                'status', 'refund_amount', 'admin_note',
                'resolved_by', 'resolved_at', 'updated_at'
            ])

            dispute.order.status = Order.Status.COMPLETED
            dispute.order.save(update_fields=['status', 'updated_at'])

            try:
                from notifications.services import notify_system
                notify_system(
                    user=dispute.buyer,
                    title='อนุมัติคืนเงินบางส่วน',
                    message=f'คำสั่งซื้อ "{dispute.order.product.name}" ได้รับการอนุมัติคืนเงิน ฿{refund_amount:,.0f}',
                    link=f'/orders/{dispute.order.id}/'
                )
            except Exception:
                pass
            messages.success(request, f'อนุมัติคืนเงินบางส่วน ฿{refund_amount:,.0f} เรียบร้อย')

        elif action == 'reject':
            dispute.status = DisputeCase.Status.RESOLVED_REJECTED
            dispute.admin_note = request.POST.get('admin_note', '').strip()
            dispute.resolved_by = request.user
            dispute.resolved_at = timezone.now()
            dispute.save(update_fields=[
                'status', 'admin_note', 'resolved_by', 'resolved_at', 'updated_at'
            ])

            dispute.order.status = Order.Status.SHIPPED
            dispute.order.save(update_fields=['status', 'updated_at'])

            try:
                from notifications.services import notify_system
                notify_system(
                    user=dispute.buyer,
                    title='เคสข้อพิพาทถูกปฏิเสธ',
                    message=f'คำสั่งซื้อ "{dispute.order.product.name}" ไม่ผ่านการอนุมัติคืนเงิน',
                    link=f'/orders/{dispute.order.id}/'
                )
            except Exception:
                pass
            messages.success(request, 'ปฏิเสธการคืนเงินเรียบร้อย')

        return redirect('dashboard:dispute_detail', dispute_id=dispute_id)

class AdminProductListView(StaffRequiredMixin, TemplateView):
    """หน้าจัดการสินค้าทั้งหมดสำหรับแอดมิน"""
    template_name = 'dashboard/admin_product_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        category = self.request.GET.get('category')
        q = self.request.GET.get('q')
        
        products = Product.objects.select_related('seller').all()
        
        if category:
            products = products.filter(category=category)
        
        if q:
            products = products.filter(name__icontains=q)
            
        context['products'] = products.order_by('-created_at')
        context['categories'] = Product.Category.choices
        context['current_category'] = category
        context['search_query'] = q
        
        return context

    def post(self, request):
        if 'delete_product' in request.POST:
            product_id = request.POST.get('product_id')
            product = get_object_or_404(Product, id=product_id)
            product.delete()
            messages.success(request, f'ลบสินค้า "{product.name}" เรียบร้อยแล้ว')
        return redirect('dashboard:admin_product_list')


class AdminAuctionListView(StaffRequiredMixin, TemplateView):
    """หน้าจัดการการประมูลสำหรับแอดมิน"""
    template_name = 'dashboard/admin_auction_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        status = self.request.GET.get('status')
        auctions = Auction.objects.select_related('product', 'seller').all()
        
        if status:
            auctions = auctions.filter(status=status)
            
        context['auctions'] = auctions.order_by('-created_at')
        context['statuses'] = Auction.Status.choices
        context['current_status'] = status
        
        return context

    def post(self, request):
        if 'delete_auction' in request.POST:
            auction_id = request.POST.get('auction_id')
            auction = get_object_or_404(Auction, id=auction_id)
            auction.delete()
            messages.success(request, f'ลบการประมูล "{auction.product.name}" เรียบร้อยแล้ว')
            
        return redirect('dashboard:admin_auction_list')


class AdminLiveStreamListView(StaffRequiredMixin, TemplateView):
    """หน้าจัดการไลฟ์สตรีมสำหรับแอดมิน"""
    template_name = 'dashboard/admin_livestream_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        streams = LiveStream.objects.select_related('host').all()
        context['streams'] = streams.order_by('-created_at')
        return context

    def post(self, request):
        if 'delete_stream' in request.POST:
            stream_id = request.POST.get('stream_id')
            stream = get_object_or_404(LiveStream, id=stream_id)
            stream.delete()
            messages.success(request, f'ลบไลฟ์สตรีม "{stream.title}" เรียบร้อยแล้ว')
        return redirect('dashboard:admin_livestream_list')


class AdminListingsView(StaffRequiredMixin, TemplateView):
    template_name = 'dashboard/admin_listings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        status_filter = self.request.GET.get('status', 'pending')
        type_filter = self.request.GET.get('type', 'marketplace')

        if status_filter == 'all':
            products = Product.objects.all()
        else:
            products = Product.objects.filter(status=status_filter)

        # Filter by type: marketplace (no auction) or auction (has auction)
        if type_filter == 'auction':
            products = products.filter(auction__isnull=False)
        else:
            products = products.filter(auction__isnull=True)

        context['products'] = products.select_related('seller').order_by('-created_at')
        context['status_filter'] = status_filter
        context['type_filter'] = type_filter

        # Counts based on type filter
        if type_filter == 'auction':
            base_qs = Product.objects.filter(auction__isnull=False)
        else:
            base_qs = Product.objects.filter(auction__isnull=True)

        context['count_pending'] = base_qs.filter(status=Product.Status.PENDING).count()
        context['count_approved'] = base_qs.filter(status=Product.Status.APPROVED).count()
        context['count_rejected'] = base_qs.filter(status=Product.Status.REJECTED).count()
        context['count_all'] = base_qs.count()
        
        context['listings'] = context['products']  # Alias for compatibility

        return context


class AdminListingActionView(StaffRequiredMixin, View):
    def post(self, request, pk):
        from notifications.services import notify_system

        product = get_object_or_404(Product, pk=pk)
        action = request.POST.get('action')
        rejection_reason = request.POST.get('rejection_reason', '').strip()

        if action == 'approve':
            product.status = Product.Status.APPROVED
            product.approved_at = timezone.now()
            product.approved_by = request.user
            product.rejected_at = None
            product.rejected_by = None
            product.rejection_reason = ''
            product.save(update_fields=[
                'status', 'approved_at', 'approved_by',
                'rejected_at', 'rejected_by', 'rejection_reason'
            ])

            # Start auction timer if product has an auction that hasn't started yet
            if hasattr(product, 'auction') and product.auction.start_at is None:
                auction = product.auction
                auction.start_at = timezone.now()
                auction.end_at = auction.start_at + timedelta(minutes=auction.duration_minutes)
                auction.save(update_fields=['start_at', 'end_at'])

            notify_system(
                user=product.seller,
                title='ประกาศได้รับการอนุมัติ',
                message=f'ประกาศ "{product.name}" ได้รับการอนุมัติแล้ว',
                link=product.get_absolute_url()
            )
            messages.success(request, 'อนุมัติประกาศเรียบร้อยแล้ว')
        elif action == 'reject':
            product.status = Product.Status.REJECTED
            product.rejected_at = timezone.now()
            product.rejected_by = request.user
            product.rejection_reason = rejection_reason
            product.approved_at = None
            product.approved_by = None
            product.save(update_fields=[
                'status', 'rejected_at', 'rejected_by',
                'rejection_reason', 'approved_at', 'approved_by'
            ])
            notify_system(
                user=product.seller,
                title='ประกาศถูกปฏิเสธ',
                message=f'ประกาศ "{product.name}" ถูกปฏิเสธ{f" (เหตุผล: {rejection_reason})" if rejection_reason else ""}',
                link=product.get_absolute_url()
            )
            messages.success(request, 'ปฏิเสธประกาศเรียบร้อยแล้ว')
        elif action == 'delete':
            try:
                product.delete()
                messages.success(request, 'ลบประกาศเรียบร้อยแล้ว')
            except Exception:
                messages.error(request, 'ไม่สามารถลบประกาศนี้ได้ เนื่องจากมีคำสั่งซื้อที่เกี่ยวข้อง กรุณาลบคำสั่งซื้อก่อน')
        else:
            messages.error(request, 'คำสั่งไม่ถูกต้อง')

        return redirect(request.META.get('HTTP_REFERER', 'dashboard:admin_listings'))

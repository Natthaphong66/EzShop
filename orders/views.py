from django.views.generic import View, DetailView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.db import transaction

from .models import Order, DisputeCase
from products.models import Product


class CreateOrderView(LoginRequiredMixin, View):
    """สร้าง Order ใหม่จาก Product"""
    
    def get(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        
        # ห้ามซื้อสินค้าตัวเอง
        if product.seller == request.user:
            messages.error(request, 'ไม่สามารถซื้อสินค้าของตัวเองได้')
            return redirect('products:product_detail', pk=product_id)

        # สินค้าขายไปแล้ว
        if product.is_sold:
            messages.error(request, 'สินค้านี้ถูกขายไปแล้ว')
            return redirect('products:product_detail', pk=product_id)

        # เช็คว่ามี order ที่ยังไม่เสร็จอยู่หรือไม่ (ทุกผู้ซื้อ)
        product_active_order = Order.objects.filter(
            product=product,
            status__in=[
                Order.Status.PENDING_PAYMENT,
                Order.Status.ESCROW_HELD,
                Order.Status.SHIPPED,
                Order.Status.COMPLETED,
            ]
        ).first()
        if product_active_order:
            if product_active_order.buyer_id == request.user.id:
                return redirect('orders:order_detail', order_id=product_active_order.id)
            messages.error(request, 'สินค้านี้มีผู้ทำรายการอยู่แล้ว')
            return redirect('products:product_detail', pk=product_id)
        
        # เช็คว่ามี order ที่ยังไม่เสร็จอยู่หรือไม่
        existing_order = Order.objects.filter(
            buyer=request.user,
            product=product,
            status__in=[
                Order.Status.PENDING_PAYMENT,
                Order.Status.ESCROW_HELD,
                Order.Status.SHIPPED,
            ]
        ).first()
        
        if existing_order:
            return redirect('orders:order_detail', order_id=existing_order.id)
        
        context = {
            'product': product,
        }
        return render(request, 'orders/create_order.html', context)
    
    def post(self, request, product_id):
        with transaction.atomic():
            product = get_object_or_404(Product.objects.select_for_update(), id=product_id)
        
            # ห้ามซื้อสินค้าตัวเอง
            if product.seller == request.user:
                messages.error(request, 'ไม่สามารถซื้อสินค้าของตัวเองได้')
                return redirect('products:product_detail', pk=product_id)

            # สินค้าขายไปแล้ว
            if product.is_sold:
                messages.error(request, 'สินค้านี้ถูกขายไปแล้ว')
                return redirect('products:product_detail', pk=product_id)

            # เช็คว่ามี order ที่ยังไม่เสร็จอยู่หรือไม่ (ทุกผู้ซื้อ)
            product_active_order = Order.objects.filter(
                product=product,
                status__in=[
                    Order.Status.PENDING_PAYMENT,
                    Order.Status.ESCROW_HELD,
                    Order.Status.SHIPPED,
                    Order.Status.COMPLETED,
                ]
            ).first()
            if product_active_order:
                if product_active_order.buyer_id == request.user.id:
                    return redirect('orders:order_detail', order_id=product_active_order.id)
                messages.error(request, 'สินค้านี้มีผู้ทำรายการอยู่แล้ว')
                return redirect('products:product_detail', pk=product_id)
        
            # สร้าง Order ใหม่
            order = Order.objects.create(
                buyer=request.user,
                seller=product.seller,
                product=product,
                amount=product.price,
                status=Order.Status.PENDING_PAYMENT,
            )
        
        messages.success(request, 'สร้างคำสั่งซื้อเรียบร้อย กรุณาชำระเงิน')
        return redirect('orders:order_detail', order_id=order.id)


class OrderDetailView(LoginRequiredMixin, DetailView):
    """แสดงรายละเอียด Order"""
    model = Order
    template_name = 'orders/order_detail.html'
    context_object_name = 'order'
    pk_url_kwarg = 'order_id'
    
    def get_queryset(self):
        # เฉพาะ buyer หรือ seller เท่านั้นที่ดูได้
        from django.db.models import Q
        return Order.objects.filter(
            Q(buyer=self.request.user) | Q(seller=self.request.user)
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.conf import settings
        context['STRIPE_PUBLISHABLE_KEY'] = settings.STRIPE_PUBLISHABLE_KEY
        return context


class MyOrdersView(LoginRequiredMixin, ListView):
    """รายการ orders ของฉัน (ในฐานะผู้ซื้อ)"""
    model = Order
    template_name = 'orders/my_orders.html'
    context_object_name = 'orders'
    
    def get_queryset(self):
        return Order.objects.filter(buyer=self.request.user)


class MySalesView(LoginRequiredMixin, ListView):
    """รายการ sales ของฉัน (ในฐานะผู้ขาย)"""
    model = Order
    template_name = 'orders/my_sales.html'
    context_object_name = 'orders'
    
    def get_queryset(self):
        return Order.objects.filter(seller=self.request.user)


class CancelOrderView(LoginRequiredMixin, View):
    """ยกเลิกคำสั่งซื้อ"""
    
    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, buyer=request.user)
        
        # เช็คว่า order อยู่ในสถานะที่ยกเลิกได้
        if order.status != Order.Status.PENDING_PAYMENT:
            messages.error(request, 'ไม่สามารถยกเลิกคำสั่งซื้อได้ในขณะนี้')
            return redirect('orders:order_detail', order_id=order_id)
        
        # ยกเลิก order
        order.status = Order.Status.CANCELLED
        order.save()
        
        messages.success(request, 'ยกเลิกคำสั่งซื้อเรียบร้อยแล้ว')
        return redirect('orders:my_orders')


class ShipOrderView(LoginRequiredMixin, View):
    """ผู้ขายกรอกเลขพัสดุและยืนยันจัดส่ง"""
    
    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, seller=request.user)
        
        # เช็คว่า order อยู่ในสถานะที่สามารถจัดส่งได้
        if order.status != Order.Status.ESCROW_HELD:
            messages.error(request, 'ไม่สามารถยืนยันการจัดส่งได้ในขณะนี้')
            return redirect('orders:order_detail', order_id=order_id)
        
        tracking_number = request.POST.get('tracking_number', '').strip()
        carrier_slug = request.POST.get('carrier_slug', '').strip()
        
        if not tracking_number or not carrier_slug:
            messages.error(request, 'กรุณากรอกเลขพัสดุและเลือกบริษัทขนส่ง')
            return redirect('orders:order_detail', order_id=order_id)
        
        # หาชื่อบริษัทขนส่งจาก carrier_slug
        carrier_display = dict(Order.CARRIER_CHOICES).get(carrier_slug, carrier_slug)
        
        # อัพเดท order
        from django.utils import timezone
        order.tracking_number = tracking_number
        order.carrier_slug = carrier_slug
        order.shipping_carrier = carrier_display
        order.shipped_at = timezone.now()
        order.status = Order.Status.SHIPPED
        order.save()
        
        messages.success(request, 'ยืนยันการจัดส่งเรียบร้อยแล้ว')
        return redirect('orders:order_detail', order_id=order_id)



class ConfirmReceivedView(LoginRequiredMixin, View):
    """ผู้ซื้อยืนยันได้รับสินค้า"""
    
    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, buyer=request.user)
        
        # เช็คว่า order อยู่ในสถานะจัดส่งแล้ว
        if order.status != Order.Status.SHIPPED:
            messages.error(request, 'ไม่สามารถยืนยันการรับสินค้าได้ในขณะนี้')
            return redirect('orders:order_detail', order_id=order_id)
        
        # เปลี่ยนสถานะเป็นสำเร็จ
        order.status = Order.Status.COMPLETED
        order.save()
        
        messages.success(request, 'ยืนยันการรับสินค้าเรียบร้อยแล้ว!')
        # Redirect ไปหน้าเขียนรีวิว
        return redirect('reviews:create_review', order_id=order_id)


class ReportIssueView(LoginRequiredMixin, View):
    """หน้าแจ้งปัญหาคำสั่งซื้อพร้อมฟอร์มรายละเอียด"""

    def get(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, buyer=request.user)

        if order.status != Order.Status.SHIPPED:
            messages.error(request, 'แจ้งปัญหาได้เฉพาะคำสั่งซื้อที่อยู่ระหว่างจัดส่ง')
            return redirect('orders:order_detail', order_id=order_id)

        # เช็คว่ามี dispute อยู่แล้วหรือไม่
        if hasattr(order, 'dispute'):
            messages.info(request, 'คุณได้แจ้งปัญหาสำหรับคำสั่งซื้อนี้แล้ว')
            return redirect('orders:order_detail', order_id=order_id)

        return render(request, 'orders/report_issue.html', {'order': order})

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, buyer=request.user)

        if order.status != Order.Status.SHIPPED:
            messages.error(request, 'แจ้งปัญหาได้เฉพาะคำสั่งซื้อที่อยู่ระหว่างจัดส่ง')
            return redirect('orders:order_detail', order_id=order_id)

        if hasattr(order, 'dispute'):
            messages.info(request, 'คุณได้แจ้งปัญหาสำหรับคำสั่งซื้อนี้แล้ว')
            return redirect('orders:order_detail', order_id=order_id)

        reason = request.POST.get('reason', '').strip()
        description = request.POST.get('description', '').strip()
        bank_name = request.POST.get('bank_name', '').strip()
        bank_account_number = request.POST.get('bank_account_number', '').strip()
        bank_account_name = request.POST.get('bank_account_name', '').strip()

        # Validate required fields
        if not all([reason, description, bank_name, bank_account_number, bank_account_name]):
            messages.error(request, 'กรุณากรอกข้อมูลให้ครบทุกช่อง')
            return render(request, 'orders/report_issue.html', {'order': order})

        valid_reasons = [r[0] for r in DisputeCase.Reason.choices]
        if reason not in valid_reasons:
            messages.error(request, 'สาเหตุที่เลือกไม่ถูกต้อง')
            return render(request, 'orders/report_issue.html', {'order': order})

        with transaction.atomic():
            dispute = DisputeCase(
                order=order,
                buyer=request.user,
                reason=reason,
                description=description,
                bank_name=bank_name,
                bank_account_number=bank_account_number,
                bank_account_name=bank_account_name,
            )

            # Handle evidence images
            if request.FILES.get('evidence_1'):
                dispute.evidence_1 = request.FILES['evidence_1']
            if request.FILES.get('evidence_2'):
                dispute.evidence_2 = request.FILES['evidence_2']
            if request.FILES.get('evidence_3'):
                dispute.evidence_3 = request.FILES['evidence_3']

            dispute.save()

            order.status = Order.Status.DISPUTED
            order.save(update_fields=['status', 'updated_at'])

        try:
            from notifications.services import notify_system
            notify_system(
                user=order.seller,
                title='มีการแจ้งปัญหาคำสั่งซื้อ',
                message=f'ผู้ซื้อได้แจ้งปัญหาสำหรับคำสั่งซื้อ "{order.product.name}"\nสาเหตุ: {dispute.get_reason_display()}\nรายละเอียด: {description}',
                link=f'/orders/{order.id}/'
            )
        except Exception:
            pass

        messages.success(request, 'แจ้งปัญหาเรียบร้อยแล้ว ทีมงานจะตรวจสอบให้เร็วที่สุด')
        return redirect('orders:order_detail', order_id=order_id)


class TrackingView(LoginRequiredMixin, View):
    """หน้าติดตามพัสดุ"""
    
    def get(self, request, order_id):
        from django.db.models import Q
        order = get_object_or_404(
            Order.objects.filter(Q(buyer=request.user) | Q(seller=request.user)),
            id=order_id
        )
        
        # ต้องมีเลขพัสดุถึงจะดูได้
        if not order.tracking_number:
            messages.error(request, 'ยังไม่มีข้อมูลการจัดส่ง')
            return redirect('orders:order_detail', order_id=order_id)
        
        # เตรียมข้อมูลสำหรับ template
        from .services import TrackingService
        service = TrackingService()
        
        context = {
            'order': order,
            'carrier_display': dict(Order.CARRIER_CHOICES).get(order.carrier_slug, order.shipping_carrier),
            'deep_link_url': service.get_deep_link_url(order.tracking_number, order.carrier_slug) if order.carrier_slug else '',
        }
        
        return render(request, 'orders/tracking.html', context)

from django.views.generic import View, DetailView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.urls import reverse

from .models import Order
from products.models import Product
from payments.models import PaymentSlip
from payments.services import run_soft_verify


class CreateOrderView(LoginRequiredMixin, View):
    """สร้าง Order ใหม่จาก Product"""
    
    def get(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        
        # ห้ามซื้อสินค้าตัวเอง
        if product.seller == request.user:
            messages.error(request, 'ไม่สามารถซื้อสินค้าของตัวเองได้')
            return redirect('products:product_detail', pk=product_id)
        
        # เช็คว่ามี order ที่ยังไม่เสร็จอยู่หรือไม่
        existing_order = Order.objects.filter(
            buyer=request.user,
            product=product,
            status__in=[
                Order.Status.PENDING_PAYMENT,
                Order.Status.WAITING_SOFT_VERIFY,
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
        product = get_object_or_404(Product, id=product_id)
        
        # ห้ามซื้อสินค้าตัวเอง
        if product.seller == request.user:
            messages.error(request, 'ไม่สามารถซื้อสินค้าของตัวเองได้')
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


class UploadSlipView(LoginRequiredMixin, View):
    """อัปโหลดสลิปการโอนเงิน"""
    
    def get(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, buyer=request.user)
        
        # เช็คว่า order อยู่ในสถานะที่อัปโหลดได้
        if order.status not in [Order.Status.PENDING_PAYMENT, Order.Status.WAITING_SOFT_VERIFY]:
            messages.error(request, 'ไม่สามารถอัปโหลดสลิปได้ในขณะนี้')
            return redirect('orders:order_detail', order_id=order_id)
        
        context = {
            'order': order,
        }
        return render(request, 'orders/upload_slip.html', context)
    
    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, buyer=request.user)
        
        if order.status not in [Order.Status.PENDING_PAYMENT, Order.Status.WAITING_SOFT_VERIFY]:
            messages.error(request, 'ไม่สามารถอัปโหลดสลิปได้ในขณะนี้')
            return redirect('orders:order_detail', order_id=order_id)
        
        slip_image = request.FILES.get('slip_image')
        if not slip_image:
            messages.error(request, 'กรุณาเลือกรูปสลิป')
            return redirect('orders:upload_slip', order_id=order_id)
        
        # ลบสลิปเก่าถ้ามี
        if hasattr(order, 'payment_slip'):
            order.payment_slip.delete()
        
        # สร้างสลิปใหม่
        slip = PaymentSlip.objects.create(
            order=order,
            image=slip_image,
        )
        
        # อัปเดตสถานะ order
        order.status = Order.Status.WAITING_SOFT_VERIFY
        order.save()
        
        # รัน soft verify
        run_soft_verify(slip)
        
        # Refresh order เพื่อดูสถานะใหม่
        order.refresh_from_db()
        
        if slip.verify_status == PaymentSlip.VerifyStatus.PASSED:
            messages.success(request, 'ตรวจสอบสลิปเรียบร้อย! เงินอยู่ในระบบแล้ว')
        elif slip.verify_status == PaymentSlip.VerifyStatus.MISMATCH:
            messages.warning(request, f'ข้อมูลไม่ตรงกัน: {slip.verify_message}')
        else:
            messages.info(request, 'อัปโหลดสลิปเรียบร้อย รอตรวจสอบ')
        
        return redirect('orders:order_detail', order_id=order_id)


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
        if order.status not in [Order.Status.PENDING_PAYMENT, Order.Status.WAITING_SOFT_VERIFY]:
            messages.error(request, 'ไม่สามารถยกเลิกคำสั่งซื้อได้ในขณะนี้')
            return redirect('orders:order_detail', order_id=order_id)
        
        # ยกเลิก order
        order.status = Order.Status.CANCELLED
        order.save()
        
        messages.success(request, 'ยกเลิกคำสั่งซื้อเรียบร้อยแล้ว')
        return redirect('orders:my_orders')

from django.views.generic import View, DetailView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.urls import reverse

from .models import Order
from products.models import Product


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
        
        # สร้าง tracking ใน AfterShip (async, ไม่ต้องรอ)
        try:
            from .services import AfterShipService
            service = AfterShipService()
            if service.is_api_supported(carrier_slug):
                service.create_tracking(tracking_number, carrier_slug)
        except Exception:
            pass  # ไม่ต้อง error ถ้า AfterShip ล้มเหลว
        
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
        from .services import AfterShipService
        service = AfterShipService()
        
        context = {
            'order': order,
            'carrier_display': dict(Order.CARRIER_CHOICES).get(order.carrier_slug, order.shipping_carrier),
            'is_api_supported': service.is_api_supported(order.carrier_slug) if order.carrier_slug else False,
            'deep_link_url': service.get_deep_link_url(order.tracking_number, order.carrier_slug) if order.carrier_slug else '',
        }
        
        return render(request, 'orders/tracking.html', context)


class TrackingAPIView(LoginRequiredMixin, View):
    """API endpoint สำหรับดึงข้อมูล tracking จาก AfterShip"""
    
    def get(self, request, order_id):
        from django.http import JsonResponse
        from django.db.models import Q
        
        order = get_object_or_404(
            Order.objects.filter(Q(buyer=request.user) | Q(seller=request.user)),
            id=order_id
        )
        
        if not order.tracking_number or not order.carrier_slug:
            return JsonResponse({
                'success': False,
                'error': 'ไม่มีข้อมูลการจัดส่ง'
            })
        
        from .services import AfterShipService
        service = AfterShipService()
        
        # ตรวจสอบว่า carrier รองรับ API หรือไม่
        if not service.is_api_supported(order.carrier_slug):
            return JsonResponse({
                'success': False,
                'use_deep_link': True,
                'deep_link_url': service.get_deep_link_url(order.tracking_number, order.carrier_slug),
                'carrier_name': dict(Order.CARRIER_CHOICES).get(order.carrier_slug, order.carrier_slug),
            })
        
        # เรียก AfterShip API
        result = service.get_tracking(order.tracking_number, order.carrier_slug)
        
        if result.get('success'):
            data = result.get('data', {})
            checkpoints = data.get('checkpoints', [])
            
            # แปลง checkpoints ให้อยู่ในรูปแบบที่ใช้งานง่าย
            formatted_checkpoints = []
            for cp in checkpoints:
                formatted_checkpoints.append({
                    'message': cp.get('message', cp.get('checkpoint_message', '')),
                    'location': cp.get('location', cp.get('city', '')),
                    'datetime': cp.get('checkpoint_time', ''),
                    'tag': cp.get('tag', ''),
                    'subtag': cp.get('subtag', ''),
                })
            
            return JsonResponse({
                'success': True,
                'data': {
                    'tag': data.get('tag', 'Pending'),
                    'tag_thai': service.translate_tag(data.get('tag', 'Pending')),
                    'tag_color': service.get_tag_color(data.get('tag', 'Pending')),
                    'subtag_message': data.get('subtag_message', ''),
                    'checkpoints': formatted_checkpoints,
                    'expected_delivery': data.get('expected_delivery'),
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'ไม่สามารถดึงข้อมูลได้'),
                'use_deep_link': True,
                'deep_link_url': service.get_deep_link_url(order.tracking_number, order.carrier_slug),
            })



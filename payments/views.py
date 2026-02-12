"""
Views สำหรับ Stripe payment processing
"""
import logging
import stripe
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from orders.models import Order
from payments.services import handle_payment_success

logger = logging.getLogger(__name__)


class CreatePaymentIntentView(LoginRequiredMixin, View):
    """สร้าง Stripe Checkout Session สำหรับ order"""
    
    def post(self, request, order_id):
        order = get_object_or_404(
            Order.objects.filter(buyer=request.user),
            id=order_id
        )
        
        # Check if order can be paid
        if order.status != Order.Status.PENDING_PAYMENT:
            return JsonResponse({
                'error': 'Order is not in pending payment status'
            }, status=400)
        
        try:
            # Create Stripe Checkout Session
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'thb',
                        'product_data': {
                            'name': order.product.name,
                            'description': f'Order #{str(order.id)[:8]}',
                        },
                        'unit_amount': int(order.amount * 100),  # Convert to satang
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=request.build_absolute_uri(f'/orders/{order.id}/?payment=success'),
                cancel_url=request.build_absolute_uri(f'/orders/{order.id}/?payment=cancelled'),
                metadata={
                    'order_id': str(order.id),
                    'buyer_id': str(order.buyer.id),
                    'seller_id': str(order.seller.id),
                    'product_id': str(order.product.id),
                },
                client_reference_id=str(order.id),
            )
            
            # Save checkout session ID to order (for tracking)
            order.stripe_payment_intent_id = checkout_session.id
            order.save()
            
            return JsonResponse({
                'session_id': checkout_session.id,
            })
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(View):
    """Handle Stripe webhook events"""
    
    def post(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        
        if not webhook_secret:
            return HttpResponse(status=400)
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except ValueError:
            # Invalid payload
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError:
            # Invalid signature
            return HttpResponse(status=400)
        
        # Handle the event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            order_id = session.get('metadata', {}).get('order_id') or session.get('client_reference_id')
            
            if order_id:
                try:
                    order = Order.objects.get(id=order_id)
                    # Update order status
                    order.stripe_payment_intent_id = session.get('id') or getattr(session, 'id', None)
                    order.stripe_payment_status = session.get('payment_status') or getattr(session, 'payment_status', None)
                    order.status = Order.Status.ESCROW_HELD
                    order.save()

                    # Mark product as sold
                    if not order.product.is_sold:
                        order.product.is_sold = True
                        order.product.save(update_fields=["is_sold"])
                    
                    # Send notifications (if notification service exists)
                    try:
                        from notifications.services import notify_order_paid
                        notify_order_paid(order)
                    except ImportError:
                        pass  # Notification service not available
                except Order.DoesNotExist:
                    logger.warning("Order %s not found", order_id)
                except Exception as e:
                    logger.error("Error handling payment success: %s", e)
        
        elif event['type'] == 'payment_intent.succeeded':
            # Also handle payment_intent.succeeded for compatibility
            payment_intent = event['data']['object']
            try:
                handle_payment_success(payment_intent['id'])
            except Exception as e:
                logger.error("Error handling payment success: %s", e)
        
        return HttpResponse(status=200)

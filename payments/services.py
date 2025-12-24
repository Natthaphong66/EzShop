"""
Service functions สำหรับจัดการการชำระเงินด้วย Stripe
"""
import stripe
from django.conf import settings

# Set Stripe API key
stripe.api_key = settings.STRIPE_SECRET_KEY


def create_payment_intent(order, amount):
    """
    สร้าง Stripe Payment Intent สำหรับ order
    
    Args:
        order: Order instance
        amount: Decimal amount in THB
        
    Returns:
        payment_intent: Stripe Payment Intent object
    """
    try:
        # Convert amount to cents (Stripe uses smallest currency unit)
        # For THB, 1 THB = 100 satang, but Stripe supports THB directly
        amount_in_satang = int(amount * 100)
        
        payment_intent = stripe.PaymentIntent.create(
            amount=amount_in_satang,
            currency='thb',
            metadata={
                'order_id': str(order.id),
                'buyer_id': str(order.buyer.id),
                'seller_id': str(order.seller.id),
                'product_id': str(order.product.id),
            },
            automatic_payment_methods={
                'enabled': True,
            },
        )
        
        return payment_intent
    except stripe.error.StripeError as e:
        raise Exception(f"Stripe error: {str(e)}")


def handle_payment_success(payment_intent_id):
    """
    จัดการเมื่อ payment สำเร็จ (เรียกจาก webhook)
    
    Args:
        payment_intent_id: Stripe Payment Intent ID
        
    Returns:
        order: Order instance ที่ถูกอัปเดต
    """
    from orders.models import Order
    
    try:
        # Get payment intent from Stripe
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        order_id = payment_intent.metadata.get('order_id')
        
        if not order_id:
            raise ValueError("Order ID not found in payment intent metadata")
        
        # Get order
        order = Order.objects.get(id=order_id)
        
        # Update order status
        order.stripe_payment_intent_id = payment_intent_id
        order.stripe_payment_status = payment_intent.status
        order.status = Order.Status.ESCROW_HELD
        order.save()
        
        # Send notifications (if notification service exists)
        try:
            from notifications.services import notify_order_paid
            notify_order_paid(order)
        except ImportError:
            pass  # Notification service not available
        
        return order
    except Order.DoesNotExist:
        raise ValueError(f"Order {order_id} not found")
    except stripe.error.StripeError as e:
        raise Exception(f"Stripe error: {str(e)}")

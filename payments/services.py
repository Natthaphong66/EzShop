"""
Service functions สำหรับจัดการการชำระเงินด้วย Stripe
"""
from decimal import Decimal

import stripe
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from payments.models import Wallet, SellerBankAccount, WithdrawalRequest

# Set Stripe API key
stripe.api_key = settings.STRIPE_SECRET_KEY


def _get_platform_fee_rate() -> Decimal:
    fee_rate = getattr(settings, 'PLATFORM_FEE_RATE', Decimal('0.05'))
    return Decimal(str(fee_rate))


def settle_completed_order_to_wallet(order, gross_amount=None):
    """
    เพิ่มยอดเข้าวอลเล็ทผู้ขายเมื่อออเดอร์สำเร็จ (กันเครดิตซ้ำ)

    Args:
        order: Order instance
        gross_amount: จำนวนเงินตั้งต้นก่อนหักค่าธรรมเนียม (ถ้า None จะใช้ order.amount)

    Returns:
        dict: {'credited': bool, 'net_amount': Decimal}
    """
    from orders.models import Order

    gross = Decimal(str(gross_amount if gross_amount is not None else order.amount))
    if gross <= 0:
        return {'credited': False, 'net_amount': Decimal('0.00')}

    fee_rate = _get_platform_fee_rate()
    fee_amount = (gross * fee_rate).quantize(Decimal('0.01'))
    net_amount = (gross - fee_amount).quantize(Decimal('0.01'))
    if net_amount <= 0:
        return {'credited': False, 'net_amount': Decimal('0.00')}

    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(id=order.id)
        if locked_order.seller_wallet_credited:
            return {'credited': False, 'net_amount': net_amount}

        wallet, _ = Wallet.objects.select_for_update().get_or_create(seller=locked_order.seller)
        wallet.balance = (wallet.balance + net_amount).quantize(Decimal('0.01'))
        wallet.save(update_fields=['balance', 'updated_at'])

        locked_order.seller_wallet_credited = True
        locked_order.save(update_fields=['seller_wallet_credited', 'updated_at'])

    return {'credited': True, 'net_amount': net_amount}


def create_withdrawal_request(*, seller, amount, note=''):
    amount = Decimal(str(amount)).quantize(Decimal('0.01'))
    if amount <= 0:
        raise ValueError('จำนวนเงินต้องมากกว่า 0')

    with transaction.atomic():
        wallet, _ = Wallet.objects.select_for_update().get_or_create(seller=seller)
        bank_account = SellerBankAccount.objects.filter(seller=seller).first()
        if not bank_account:
            raise ValueError('กรุณาบันทึกบัญชีธนาคารก่อนถอนเงิน')

        if wallet.balance < amount:
            raise ValueError('ยอดเงินคงเหลือไม่เพียงพอ')

        wallet.balance = (wallet.balance - amount).quantize(Decimal('0.01'))
        wallet.locked_balance = (wallet.locked_balance + amount).quantize(Decimal('0.01'))
        wallet.save(update_fields=['balance', 'locked_balance', 'updated_at'])

        withdrawal = WithdrawalRequest.objects.create(
            seller=seller,
            wallet=wallet,
            amount=amount,
            bank_name=bank_account.bank_name,
            bank_account_number=bank_account.account_number,
            bank_account_name=bank_account.account_name,
            note=note,
        )

    return withdrawal


def complete_withdrawal_request(*, withdrawal, admin_user, admin_note='', transfer_slip=None):
    if withdrawal.status != WithdrawalRequest.Status.PENDING:
        raise ValueError('คำขอนี้ไม่ได้อยู่ในสถานะรอดำเนินการ')

    with transaction.atomic():
        locked_withdrawal = WithdrawalRequest.objects.select_for_update().get(id=withdrawal.id)
        wallet = Wallet.objects.select_for_update().get(id=locked_withdrawal.wallet_id)

        if locked_withdrawal.status != WithdrawalRequest.Status.PENDING:
            raise ValueError('คำขอนี้ถูกดำเนินการไปแล้ว')

        if wallet.locked_balance < locked_withdrawal.amount:
            raise ValueError('ยอดเงินอายัดไม่เพียงพอสำหรับคำขอนี้')

        wallet.locked_balance = (wallet.locked_balance - locked_withdrawal.amount).quantize(Decimal('0.01'))
        wallet.save(update_fields=['locked_balance', 'updated_at'])

        locked_withdrawal.status = WithdrawalRequest.Status.COMPLETED
        locked_withdrawal.admin_note = admin_note
        locked_withdrawal.processed_by = admin_user
        locked_withdrawal.processed_at = timezone.now()
        if transfer_slip:
            locked_withdrawal.transfer_slip = transfer_slip
        locked_withdrawal.save(update_fields=[
            'status', 'admin_note', 'processed_by', 'processed_at',
            'transfer_slip', 'updated_at'
        ])


def reject_withdrawal_request(*, withdrawal, admin_user, admin_note=''):
    if withdrawal.status != WithdrawalRequest.Status.PENDING:
        raise ValueError('คำขอนี้ไม่ได้อยู่ในสถานะรอดำเนินการ')

    with transaction.atomic():
        locked_withdrawal = WithdrawalRequest.objects.select_for_update().get(id=withdrawal.id)
        wallet = Wallet.objects.select_for_update().get(id=locked_withdrawal.wallet_id)

        if locked_withdrawal.status != WithdrawalRequest.Status.PENDING:
            raise ValueError('คำขอนี้ถูกดำเนินการไปแล้ว')

        if wallet.locked_balance < locked_withdrawal.amount:
            raise ValueError('ยอดเงินอายัดไม่เพียงพอสำหรับคำขอนี้')

        wallet.locked_balance = (wallet.locked_balance - locked_withdrawal.amount).quantize(Decimal('0.01'))
        wallet.balance = (wallet.balance + locked_withdrawal.amount).quantize(Decimal('0.01'))
        wallet.save(update_fields=['balance', 'locked_balance', 'updated_at'])

        locked_withdrawal.status = WithdrawalRequest.Status.REJECTED
        locked_withdrawal.admin_note = admin_note
        locked_withdrawal.processed_by = admin_user
        locked_withdrawal.processed_at = timezone.now()
        locked_withdrawal.save(update_fields=[
            'status', 'admin_note', 'processed_by', 'processed_at', 'updated_at'
        ])


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
        
        return order
    except Order.DoesNotExist:
        raise ValueError(f"Order {order_id} not found")
    except stripe.error.StripeError as e:
        raise Exception(f"Stripe error: {str(e)}")

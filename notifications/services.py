"""
Service functions สำหรับสร้าง notifications
"""
from django.urls import reverse
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Notification


def send_notification_websocket(user, notification):
    """Send notification via WebSocket"""
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            from django.utils import timezone
            from datetime import timedelta
            
            # Calculate time ago
            diff = timezone.now() - notification.created_at
            if diff.days > 0:
                time_ago = f'{diff.days} วันที่แล้ว' if diff.days > 1 else 'เมื่อวาน'
            elif diff.seconds // 3600 > 0:
                time_ago = f'{diff.seconds // 3600} ชั่วโมงที่แล้ว'
            elif diff.seconds // 60 > 0:
                time_ago = f'{diff.seconds // 60} นาทีที่แล้ว'
            else:
                time_ago = 'เมื่อสักครู่'
            
            notification_data = {
                'id': str(notification.id),
                'type': notification.notification_type,
                'title': notification.title,
                'message': notification.message[:100] + '...' if len(notification.message) > 100 else notification.message,
                'link': notification.link,
                'is_read': notification.is_read,
                'created_at': notification.created_at.strftime('%d/%m/%Y %H:%M'),
                'time_ago': time_ago,
            }
            
            async_to_sync(channel_layer.group_send)(
                f'notifications_{user.id}',
                {
                    'type': 'notification_created',
                    'notification': notification_data
                }
            )
    except Exception as e:
        print(f"Failed to send WebSocket notification: {e}")


def notify_auction_won(auction, winner):
    """แจ้งเตือนผู้ชนะการประมูล"""
    notification = Notification.create_notification(
        user=winner,
        notification_type=Notification.NotificationType.AUCTION_WON,
        title='ยินดีด้วย! คุณชนะการประมูล',
        message=f'คุณชนะการประมูล "{auction.product.name}" ด้วยราคา ฿{auction.final_price:,.2f}',
        link=reverse('auctions:auction_detail', args=[str(auction.id)]),
        auction=auction
    )
    send_notification_websocket(winner, notification)


def notify_outbid(auction, previous_bidder, new_amount):
    """แจ้งเตือนเมื่อถูกบิดแซง"""
    notification = Notification.create_notification(
        user=previous_bidder,
        notification_type=Notification.NotificationType.AUCTION_OUTBID,
        title='มีคนบิดแซงคุณแล้ว!',
        message=f'มีคนเสนอราคา ฿{new_amount:,.2f} สำหรับ "{auction.product.name}" บิดกลับเลย!',
        link=reverse('auctions:auction_detail', args=[str(auction.id)]),
        auction=auction
    )
    send_notification_websocket(previous_bidder, notification)


def notify_auction_ending_soon(auction, bidder):
    """แจ้งเตือนเมื่อประมูลใกล้จบ"""
    Notification.create_notification(
        user=bidder,
        notification_type=Notification.NotificationType.AUCTION_ENDING,
        title='ประมูลใกล้จบแล้ว!',
        message=f'การประมูล "{auction.product.name}" กำลังจะสิ้นสุดเร็วๆ นี้',
        link=reverse('auctions:auction_detail', args=[str(auction.id)]),
        auction=auction
    )


def notify_new_order(order):
    """แจ้งเตือนผู้ขายเมื่อมีคำสั่งซื้อใหม่"""
    notification = Notification.create_notification(
        user=order.seller,
        notification_type=Notification.NotificationType.ORDER_CREATED,
        title='มีคำสั่งซื้อใหม่!',
        message=f'คุณมีคำสั่งซื้อใหม่สำหรับ "{order.product.name}" จำนวน ฿{order.amount:,.2f}',
        link=reverse('orders:order_detail', args=[str(order.id)]),
        order=order
    )
    send_notification_websocket(order.seller, notification)


def notify_order_paid(order):
    """แจ้งเตือนผู้ขายเมื่อได้รับการชำระเงิน"""
    Notification.create_notification(
        user=order.seller,
        notification_type=Notification.NotificationType.ORDER_PAID,
        title='ได้รับการชำระเงินแล้ว!',
        message=f'คำสั่งซื้อ "{order.product.name}" ได้รับการชำระเงินแล้ว กรุณาจัดส่งสินค้า',
        link=reverse('orders:order_detail', args=[str(order.id)]),
        order=order
    )


def notify_order_shipped(order):
    """แจ้งเตือนผู้ซื้อเมื่อสินค้าถูกจัดส่ง"""
    Notification.create_notification(
        user=order.buyer,
        notification_type=Notification.NotificationType.ORDER_SHIPPED,
        title='สินค้าถูกจัดส่งแล้ว!',
        message=f'คำสั่งซื้อ "{order.product.name}" ถูกจัดส่งแล้ว',
        link=reverse('orders:order_detail', args=[str(order.id)]),
        order=order
    )


def notify_system(user, title, message, link=''):
    """แจ้งเตือนทั่วไปจากระบบ"""
    Notification.create_notification(
        user=user,
        notification_type=Notification.NotificationType.SYSTEM,
        title=title,
        message=message,
        link=link
    )


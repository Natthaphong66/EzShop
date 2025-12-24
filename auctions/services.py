"""
Service functions สำหรับจัดการหลังจบการประมูล
"""
from django.urls import reverse
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def handle_auction_winner(auction, winner):
    """
    จัดการทุกอย่างเมื่อมีผู้ชนะการประมูล:
    1. สร้าง Order อัตโนมัติ
    2. สร้าง ChatRoom ระหว่างผู้ขายและผู้ชนะ
    3. ส่ง Welcome Message
    4. ส่ง Notification ให้ทั้งคู่
    """
    from orders.models import Order
    from chats.models import ChatRoom, Message
    from notifications.services import notify_auction_won
    from notifications.models import Notification
    
    # 1. สร้าง Order อัตโนมัติ
    order = Order.objects.create(
        buyer=winner,
        seller=auction.seller,
        product=auction.product,
        amount=auction.final_price,
        status=Order.Status.PENDING_PAYMENT,
    )
    
    # 2. สร้าง ChatRoom (ถ้ายังไม่มี)
    # หา ChatRoom ที่มีอยู่แล้วระหว่าง 2 คนนี้สำหรับ auction นี้
    existing_room = ChatRoom.objects.filter(
        participants=winner
    ).filter(
        participants=auction.seller
    ).filter(
        auction=auction
    ).first()
    
    if existing_room:
        chat_room = existing_room
    else:
        # สร้าง ChatRoom ใหม่
        chat_room = ChatRoom.objects.create(
            product=auction.product,
            auction=auction
        )
        chat_room.participants.add(winner, auction.seller)
    
    # 3. ส่ง Welcome Message (System Message)
    welcome_message = f"""🎉 ยินดีด้วย! การประมูลสิ้นสุดแล้ว

📦 สินค้า: {auction.product.name}
💰 ราคาชนะ: ฿{auction.final_price:,.2f}
🏆 ผู้ชนะ: {winner.get_full_name_display()}

คุณสามารถชำระเงินได้ในแชทเลยนะ """
    
    Message.objects.create(
        room=chat_room,
        sender=auction.seller,  # ส่งในนามผู้ขาย
        content=welcome_message,
    )
    
    # 4. ส่ง Notification ให้ผู้ชนะ
    notify_auction_won(auction, winner)
    
    # 5. ส่ง Notification ให้ผู้ขาย
    order_url = reverse('orders:order_detail', args=[str(order.id)])
    chat_url = reverse('chats:room', args=[str(chat_room.id)])
    
    seller_notification = Notification.create_notification(
        user=auction.seller,
        notification_type=Notification.NotificationType.ORDER_CREATED,
        title='🎉 การประมูลจบแล้ว! มีผู้ชนะ',
        message=f'การประมูล "{auction.product.name}" จบลงแล้ว ผู้ชนะคือ {winner.get_full_name_display()} ด้วยราคา ฿{auction.final_price:,.2f}',
        link=chat_url,
        auction=auction,
        order=order
    )
    
    # Send WebSocket notification to seller
    from notifications.services import send_notification_websocket
    send_notification_websocket(auction.seller, seller_notification)
    
    return {
        'order': order,
        'chat_room': chat_room,
    }


def send_bid_websocket(auction, bid):
    """Send new bid information via WebSocket to all viewers"""
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            # Refresh auction to get updated bid count
            auction.refresh_from_db()
            
            bid_data = {
                'id': str(bid.id),
                'bidder_name': bid.bidder.get_full_name_display(),
                'bidder_profile_picture': bid.bidder.profile_picture.url if bid.bidder.profile_picture else None,
                'amount': str(bid.amount),
                'created_at': bid.created_at.isoformat(),
                'created_at_display': bid.created_at.strftime('%d/%m/%Y %H:%M:%S'),
                'current_price': str(bid.amount),
                'bid_count': auction.bids.count(),
            }
            
            async_to_sync(channel_layer.group_send)(
                f'auction_{auction.id}',
                {
                    'type': 'new_bid',
                    'bid_data': bid_data
                }
            )
    except Exception as e:
        print(f"Failed to send bid WebSocket: {e}")


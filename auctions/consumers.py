import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class AuctionConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time auction bidding"""

    async def connect(self):
        self.auction_id = self.scope['url_route']['kwargs']['auction_id']
        self.auction_group_name = f'auction_{self.auction_id}'
        self.user = self.scope['user']

        # Check if user is authenticated
        if not self.user.is_authenticated:
            await self.close()
            return

        # Check if auction exists and is accessible
        auction_exists = await self.check_auction_exists()
        if not auction_exists:
            await self.close()
            return

        # Join auction group
        await self.channel_layer.group_add(
            self.auction_group_name,
            self.channel_name
        )

        await self.accept()

        # Send current auction state on connect
        auction_data = await self.get_auction_data()
        await self.send(text_data=json.dumps({
            'type': 'auction_state',
            'data': auction_data
        }))

    async def disconnect(self, close_code):
        # Leave auction group
        await self.channel_layer.group_discard(
            self.auction_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Handle incoming messages from WebSocket"""
        data = json.loads(text_data)
        message_type = data.get('type')

        if message_type == 'get_bid_history':
            # Send bid history
            bid_history = await self.get_bid_history()
            await self.send(text_data=json.dumps({
                'type': 'bid_history',
                'data': bid_history
            }))

    async def new_bid(self, event):
        """Send new bid information to all connected clients"""
        bid_data = event['bid_data']
        await self.send(text_data=json.dumps({
            'type': 'new_bid',
            'data': bid_data
        }))

    async def auction_ended(self, event):
        """Notify when auction ends"""
        await self.send(text_data=json.dumps({
            'type': 'auction_ended',
            'data': event['data']
        }))

    @database_sync_to_async
    def check_auction_exists(self):
        """Check if auction exists"""
        from .models import Auction
        return Auction.objects.filter(id=self.auction_id).exists()

    @database_sync_to_async
    def get_auction_data(self):
        """Get current auction data"""
        from .models import Auction
        from django.utils import timezone
        
        try:
            auction = Auction.objects.select_related('product', 'seller').prefetch_related('bids__bidder').get(id=self.auction_id)
            
            highest_bid = auction.bids.order_by('-amount').first()
            current_price = highest_bid.amount if highest_bid else auction.starting_price
            
            return {
                'current_price': str(current_price),
                'bid_count': auction.bids.count(),
                'status': auction.status,
                'end_at': auction.end_at.isoformat() if auction.end_at else None,
                'is_ended': auction.status == Auction.Status.ENDED or (auction.end_at is not None and auction.end_at <= timezone.now()),
            }
        except Auction.DoesNotExist:
            return None

    @database_sync_to_async
    def get_bid_history(self, limit=20):
        """Get bid history for the auction"""
        from .models import Bid
        
        bids = Bid.objects.filter(
            auction_id=self.auction_id
        ).select_related('bidder').order_by('-created_at')[:limit]
        
        return [
            {
                'id': str(bid.id),
                'bidder_name': bid.bidder.get_full_name_display(),
                'bidder_profile_picture': bid.bidder.profile_picture.url if bid.bidder.profile_picture else None,
                'amount': str(bid.amount),
                'created_at': bid.created_at.isoformat(),
                'created_at_display': bid.created_at.strftime('%d/%m/%Y %H:%M:%S'),
            }
            for bid in bids
        ]


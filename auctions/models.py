import uuid
from django.db import models
from django.conf import settings
from products.models import Product
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

class Auction(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        LIVE = 'live', 'Live'
        ENDED = 'ended', 'Ended'
        CANCELED = 'canceled', 'Canceled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='auction')
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='auctions')
    
    starting_price = models.DecimalField(max_digits=12, decimal_places=2)
    min_increment = models.DecimalField(max_digits=12, decimal_places=2)
    reserve_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    
    winner_bid = models.OneToOneField('Bid', on_delete=models.SET_NULL, null=True, blank=True, related_name='won_auction')
    final_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['seller']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Auction for {self.product.name}"
    
    @property
    def current_price(self):
        """Return the current highest bid amount, or None if no bids yet"""
        highest_bid = self.bids.order_by('-amount').first()
        return highest_bid.amount if highest_bid else None

    def close_auction(self):
        """Close the auction and determine the winner"""
        from django.utils import timezone
        
        if self.status == self.Status.ENDED:
            return

        # Find the highest bid
        highest_bid = self.bids.order_by('-amount').first()
        
        self.status = self.Status.ENDED
        self.ended_at = timezone.now()
        
        if highest_bid:
            # Check if highest bid meets reserve price (if set)
            if self.reserve_price and highest_bid.amount < self.reserve_price:
                # Reserve not met - no winner
                self.winner_bid = None
                self.final_price = highest_bid.amount  # Record final bid but no winner
            else:
                # Reserve met or no reserve - declare winner
                self.winner_bid = highest_bid
                self.final_price = highest_bid.amount
            
            # Send email to winner only if reserve was met
            if self.winner_bid:
                try:
                    subject = render_to_string('auctions/emails/winner_notification_subject.txt', {'auction': self})
                    # Force single line subject to avoid HeaderParseError
                    subject = ''.join(subject.splitlines())
                    
                    html_content = render_to_string('auctions/emails/winner_notification_body.html', {
                        'auction': self,
                        'user': highest_bid.bidder
                    })
                    text_content = render_to_string('auctions/emails/winner_notification_body.txt', {
                        'auction': self,
                        'user': highest_bid.bidder
                    })
                    
                    msg = EmailMultiAlternatives(
                        subject,
                        text_content,
                        settings.DEFAULT_FROM_EMAIL,
                        [highest_bid.bidder.email]
                    )
                    msg.attach_alternative(html_content, "text/html")
                    msg.send()
                except Exception as e:
                    print(f"Failed to send winner email: {e}")
        
        self.save()

class Bid(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='bids')
    bidder = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bids')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['auction', 'created_at']),
            models.Index(fields=['auction', 'amount']),
            models.Index(fields=['bidder']),
        ]
        ordering = ['-amount']

    def __str__(self):
        return f"{self.bidder} bid {self.amount} on {self.auction}"

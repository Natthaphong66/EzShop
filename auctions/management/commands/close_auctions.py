from django.core.management.base import BaseCommand
from django.utils import timezone
from auctions.models import Auction

class Command(BaseCommand):
    help = 'Closes expired auctions and determines winners'

    def handle(self, *args, **options):
        now = timezone.now()
        
        # Find active auctions that have passed their end time
        expired_auctions = Auction.objects.filter(
            status=Auction.Status.LIVE,
            end_at__lte=now
        )
        
        count = 0
        for auction in expired_auctions:
            auction.close_auction()
            count += 1
            self.stdout.write(self.style.SUCCESS(f'Closed auction "{auction}"'))
            
        if count == 0:
            self.stdout.write('No expired auctions found.')
        else:
            self.stdout.write(self.style.SUCCESS(f'Successfully closed {count} auctions.'))

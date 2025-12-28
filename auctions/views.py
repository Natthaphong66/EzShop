from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.db import transaction
from django.contrib import messages
from django.http import JsonResponse
from decimal import Decimal

from .models import Auction, Bid
from .forms import AuctionForm
from products.forms import ProductForm
from products.models import Product, ProductImage

class AuctionListView(ListView):
    model = Auction
    template_name = 'auctions/auction_list.html'
    context_object_name = 'auctions'
    
    def get_queryset(self):
        from django.utils import timezone
        return Auction.objects.filter(
            status=Auction.Status.LIVE,
            end_at__gt=timezone.now()
        ).order_by('-created_at')

class AuctionDetailView(DetailView):
    model = Auction
    template_name = 'auctions/auction_detail.html'
    context_object_name = 'auction'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # Auto-close if expired but still marked as LIVE
        from django.utils import timezone
        if obj.status == Auction.Status.LIVE and obj.end_at <= timezone.now():
            obj.close_auction()
        return obj

class AuctionCreateView(LoginRequiredMixin, CreateView):
    template_name = 'auctions/auction_form.html'
    form_class = AuctionForm
    success_url = reverse_lazy('auctions:auction_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            # Create a mutable copy of POST data
            post_data = self.request.POST.copy()
            
            # Inject starting_price as price for ProductForm validation
            if 'starting_price' in post_data and 'price' not in post_data:
                post_data['price'] = post_data['starting_price']
            
            context['product_form'] = ProductForm(post_data, self.request.FILES)
        else:
            context['product_form'] = ProductForm()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        product_form = context['product_form']
        
        if product_form.is_valid():
            with transaction.atomic():
                # Get the auction starting price first
                auction_data = form.cleaned_data
                
                # 1. Save Product
                product = product_form.save(commit=False)
                product.seller = self.request.user
                # Set product price to auction starting price
                product.price = auction_data['starting_price']
                product.save()
                
                # Handle multiple images
                images = self.request.FILES.getlist('images')
                if images:
                    # Set first image as main product image
                    product.image = images[0]
                    product.save()
                    
                    # Save remaining images as ProductImage instances
                    for img in images[1:]:
                        ProductImage.objects.create(product=product, image=img)
                else:
                    # No images uploaded - auction products should have images
                    pass

                # 2. Save Auction
                auction = form.save(commit=False)
                auction.product = product
                auction.seller = self.request.user
                auction.status = Auction.Status.LIVE  # Set status to LIVE immediately
                # Set start time to now (user only selects end time)
                from django.utils import timezone
                auction.start_at = timezone.now()
                auction.save()
                
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))


class PlaceBidView(LoginRequiredMixin, View):
    """Handle bid submission for auctions"""
    
    def post(self, request, pk):
        auction = get_object_or_404(Auction, pk=pk)
        
        # Validation 1: Check if user is not the seller
        if request.user == auction.seller:
            messages.error(request, 'คุณไม่สามารถบิดสินค้าของตัวเองได้')
            return redirect('auctions:auction_detail', pk=auction.pk)
        
        # Validation 2: Check auction status is LIVE
        # Validation 2: Check auction status is LIVE and not expired
        from django.utils import timezone
        if auction.status != Auction.Status.LIVE or auction.end_at <= timezone.now():
            if auction.status == Auction.Status.LIVE:
                auction.close_auction() # Close it if it should be closed
            messages.error(request, 'การประมูลนี้จบลงแล้ว')
            return redirect('auctions:auction_detail', pk=auction.pk)
        
        # Get bid amount from form
        try:
            bid_amount = Decimal(request.POST.get('amount', 0))
        except:
            messages.error(request, 'กรุณาระบุราคาที่ถูกต้อง')
            return redirect('auctions:auction_detail', pk=auction.pk)
        
        # Calculate minimum required bid
        current_price = auction.current_price or auction.starting_price
        min_required_bid = current_price + auction.min_increment
        
        # Validation 3: Check if bid is high enough
        if bid_amount < min_required_bid:
            messages.error(
                request, 
                f'ราคาต้องสูงกว่าราคาปัจจุบัน! ราคาขั้นต่ำคือ ฿ {min_required_bid:,.2f}'
            )
            return redirect('auctions:auction_detail', pk=auction.pk)
        
        # Get previous highest bidder before creating new bid
        previous_highest_bid = auction.bids.order_by('-amount').first()
        previous_bidder = previous_highest_bid.bidder if previous_highest_bid else None
        
        # Create the bid
        with transaction.atomic():
            bid = Bid.objects.create(
                auction=auction,
                bidder=request.user,
                amount=bid_amount
            )
            
            # Send WebSocket message to all viewers
            from auctions.services import send_bid_websocket
            send_bid_websocket(auction, bid)
            
            # Notify previous bidder that they've been outbid
            if previous_bidder and previous_bidder != request.user:
                from notifications.services import notify_outbid
                notify_outbid(auction, previous_bidder, bid_amount)
        
        messages.success(request, f'บิดสำเร็จ! ราคาของคุณ: ฿ {bid_amount:,.2f}')
        return redirect('auctions:auction_detail', pk=auction.pk)


class BidHistoryView(View):
    """API endpoint to get bid history for an auction"""
    
    def get(self, request, pk):
        auction = get_object_or_404(Auction, pk=pk)
        
        bids = Bid.objects.filter(
            auction=auction
        ).select_related('bidder').order_by('-created_at')[:20]
        
        bids_data = [
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
        
        return JsonResponse({
            'success': True,
            'bids': bids_data
        })


class MyAuctionsView(LoginRequiredMixin, ListView):
    """แสดงรายการการประมูลที่ผู้ใช้สร้าง"""
    model = Auction
    template_name = 'auctions/my_auctions.html'
    context_object_name = 'auctions'
    paginate_by = 12
    
    def get_queryset(self):
        return Auction.objects.filter(
            seller=self.request.user
        ).select_related('product').prefetch_related('bids').order_by('-created_at')


class MyBidsView(LoginRequiredMixin, ListView):
    """แสดงรายการการบิดที่ผู้ใช้เคยทำ"""
    template_name = 'auctions/my_bids.html'
    context_object_name = 'bids'
    paginate_by = 12
    
    def get_queryset(self):
        # Get unique auctions that user has bid on
        auctions = Auction.objects.filter(
            bids__bidder=self.request.user
        ).distinct().select_related('product', 'seller').prefetch_related('bids').order_by('-created_at')
        
        # Add user's highest bid for each auction
        auctions_with_bid = []
        for auction in auctions:
            user_bids = auction.bids.filter(bidder=self.request.user).order_by('-amount')
            highest_bid = user_bids.first()
            current_highest_bid = auction.bids.order_by('-amount').first()
            
            auctions_with_bid.append({
                'auction': auction,
                'my_highest_bid': float(highest_bid.amount) if highest_bid else None,
                'my_bid_count': user_bids.count(),
                'is_leading': current_highest_bid.bidder == self.request.user if current_highest_bid else False,
            })
        
        return auctions_with_bid

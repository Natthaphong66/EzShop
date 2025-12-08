from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.db import transaction
from django.contrib import messages
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
                # Auction items are published immediately for now, or could be draft
                product.status = Product.Status.PUBLISHED 
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
            messages.error(request, '❌ คุณไม่สามารถบิดสินค้าของตัวเองได้')
            return redirect('auctions:auction_detail', pk=auction.pk)
        
        # Validation 2: Check auction status is LIVE
        # Validation 2: Check auction status is LIVE and not expired
        from django.utils import timezone
        if auction.status != Auction.Status.LIVE or auction.end_at <= timezone.now():
            if auction.status == Auction.Status.LIVE:
                auction.close_auction() # Close it if it should be closed
            messages.error(request, '❌ การประมูลนี้จบลงแล้ว')
            return redirect('auctions:auction_detail', pk=auction.pk)
        
        # Get bid amount from form
        try:
            bid_amount = Decimal(request.POST.get('amount', 0))
        except:
            messages.error(request, '❌ กรุณาระบุราคาที่ถูกต้อง')
            return redirect('auctions:auction_detail', pk=auction.pk)
        
        # Calculate minimum required bid
        current_price = auction.current_price or auction.starting_price
        min_required_bid = current_price + auction.min_increment
        
        # Validation 3: Check if bid is high enough
        if bid_amount < min_required_bid:
            messages.error(
                request, 
                f'❌ ราคาต้องสูงกว่าราคาปัจจุบัน! ราคาขั้นต่ำคือ ฿ {min_required_bid:,.2f}'
            )
            return redirect('auctions:auction_detail', pk=auction.pk)
        
        # Create the bid
        with transaction.atomic():
            Bid.objects.create(
                auction=auction,
                bidder=request.user,
                amount=bid_amount
            )
        
        messages.success(request, f'บิดสำเร็จ! ราคาของคุณ: ฿ {bid_amount:,.2f}')
        return redirect('auctions:auction_detail', pk=auction.pk)

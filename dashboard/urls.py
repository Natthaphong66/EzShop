from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('disputes/', views.DisputeListView.as_view(), name='dispute_list'),
    path('disputes/<uuid:dispute_id>/', views.DisputeDetailView.as_view(), name='dispute_detail'),
    
    # Management Pages
    path('products/', views.AdminProductListView.as_view(), name='admin_product_list'),
    path('auctions/', views.AdminAuctionListView.as_view(), name='admin_auction_list'),
    path('livestreams/', views.AdminLiveStreamListView.as_view(), name='admin_livestream_list'),
    path('disputes/<uuid:dispute_id>/action/', views.DisputeActionView.as_view(), name='dispute_action'),
    
    # Admin Listings
    path('listings/', views.AdminListingsView.as_view(), name='admin_listings'),
    path('listings/<uuid:pk>/action/', views.AdminListingActionView.as_view(), name='admin_listing_action'),
]

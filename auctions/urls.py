from django.urls import path
from . import views

app_name = 'auctions'

urlpatterns = [
    path('', views.AuctionListView.as_view(), name='auction_list'),
    path('create/', views.AuctionCreateView.as_view(), name='auction_create'),
    path('<uuid:pk>/', views.AuctionDetailView.as_view(), name='auction_detail'),
    path('<uuid:pk>/bid/', views.PlaceBidView.as_view(), name='place_bid'),
    path('my-auctions/', views.MyAuctionsView.as_view(), name='my_auctions'),
    path('my-bids/', views.MyBidsView.as_view(), name='my_bids'),
    path('api/<uuid:pk>/bids/', views.BidHistoryView.as_view(), name='bid_history_api'),
]

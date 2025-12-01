from django.urls import path
from . import views

app_name = 'auctions'

urlpatterns = [
    path('', views.AuctionListView.as_view(), name='auction_list'),
    path('create/', views.AuctionCreateView.as_view(), name='auction_create'),
    path('<uuid:pk>/', views.AuctionDetailView.as_view(), name='auction_detail'),
    path('<uuid:pk>/bid/', views.PlaceBidView.as_view(), name='place_bid'),
]

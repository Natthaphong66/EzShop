from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('create/<uuid:product_id>/', views.CreateOrderView.as_view(), name='create_order'),
    path('<uuid:order_id>/', views.OrderDetailView.as_view(), name='order_detail'),
    path('<uuid:order_id>/cancel/', views.CancelOrderView.as_view(), name='cancel_order'),
    path('<uuid:order_id>/ship/', views.ShipOrderView.as_view(), name='ship_order'),
    path('<uuid:order_id>/confirm-received/', views.ConfirmReceivedView.as_view(), name='confirm_received'),
    path('my-orders/', views.MyOrdersView.as_view(), name='my_orders'),
    path('my-sales/', views.MySalesView.as_view(), name='my_sales'),
]

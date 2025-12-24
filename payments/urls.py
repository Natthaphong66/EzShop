from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('create-payment-intent/<uuid:order_id>/', views.CreatePaymentIntentView.as_view(), name='create_payment_intent'),
    path('webhook/', views.StripeWebhookView.as_view(), name='stripe_webhook'),
]


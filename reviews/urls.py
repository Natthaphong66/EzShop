from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    path('create/<uuid:order_id>/', views.CreateReviewView.as_view(), name='create_review'),
    path('skip/<uuid:order_id>/', views.SkipReviewView.as_view(), name='skip_review'),
]

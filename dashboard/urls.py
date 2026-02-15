from django.urls import path
from .views import AdminDashboardView, DisputeListView, DisputeDetailView, DisputeActionView

app_name = 'dashboard'

urlpatterns = [
    path('', AdminDashboardView.as_view(), name='admin_dashboard'),
    path('disputes/', DisputeListView.as_view(), name='dispute_list'),
    path('disputes/<uuid:dispute_id>/', DisputeDetailView.as_view(), name='dispute_detail'),
    path('disputes/<uuid:dispute_id>/action/', DisputeActionView.as_view(), name='dispute_action'),
]

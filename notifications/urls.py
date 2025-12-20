from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='list'),
    path('api/dropdown/', views.NotificationDropdownView.as_view(), name='dropdown'),
    path('api/mark-read/<uuid:notification_id>/', views.MarkAsReadView.as_view(), name='mark_read'),
    path('api/mark-all-read/', views.MarkAllAsReadView.as_view(), name='mark_all_read'),
]


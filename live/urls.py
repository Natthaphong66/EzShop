from django.urls import path
from . import views

app_name = 'live'

urlpatterns = [
    path('', views.LiveStreamListView.as_view(), name='stream_list'),
    path('new/', views.LiveStreamPrepareView.as_view(), name='stream_create'),  # Renamed - goes to prepare page
    path('<uuid:pk>/cancel/', views.LiveStreamCancelView.as_view(), name='stream_cancel'),
    path('<uuid:pk>/', views.LiveStreamDetailView.as_view(), name='stream_detail'),
    path('<uuid:pk>/end/', views.LiveStreamEndView.as_view(), name='stream_end'),
    path('my-streams/', views.MyLiveStreamsView.as_view(), name='my_streams'),
    path('api/token/', views.AgoraTokenView.as_view(), name='agora_token'),
]


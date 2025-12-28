from django.urls import path
from . import views

app_name = 'live'

urlpatterns = [
    path('', views.LiveStreamListView.as_view(), name='stream_list'),
    path('create/', views.LiveStreamCreateView.as_view(), name='stream_create'),
    path('<uuid:pk>/', views.LiveStreamDetailView.as_view(), name='stream_detail'),
    path('<uuid:pk>/end/', views.LiveStreamEndView.as_view(), name='stream_end'),
    path('api/<uuid:pk>/token/', views.AgoraTokenView.as_view(), name='agora_token'),
    path('my-streams/', views.MyLiveStreamsView.as_view(), name='my_streams'),
]


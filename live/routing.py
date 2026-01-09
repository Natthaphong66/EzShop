from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/live/(?P<channel_name>[\w-]+)/$', consumers.LiveChatConsumer.as_asgi()),
]


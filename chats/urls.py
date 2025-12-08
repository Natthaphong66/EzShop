from django.urls import path
from . import views

app_name = 'chats'

urlpatterns = [
    # Chat room list - แสดงรายการห้องแชททั้งหมดของ user
    path('', views.ChatRoomListView.as_view(), name='room_list'),
    
    # Chat room detail - หน้าแชท
    path('room/<uuid:room_id>/', views.ChatRoomView.as_view(), name='room'),
    
    # Start chat with user (creates or gets existing room)
    path('start/<uuid:user_id>/', views.StartChatView.as_view(), name='start_chat'),
    
    # Start chat about a product
    path('start/product/<uuid:product_id>/', views.StartProductChatView.as_view(), name='start_product_chat'),
    
    # API endpoints for AJAX
    path('api/room/<uuid:room_id>/messages/', views.GetMessagesView.as_view(), name='get_messages'),
    path('api/room/<uuid:room_id>/send/', views.SendMessageView.as_view(), name='send_message'),
    path('api/room/<uuid:room_id>/mark-read/', views.MarkReadView.as_view(), name='mark_read'),
]

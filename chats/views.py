import json
from django.views import View
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Q, Max
from django.utils import timezone

from .models import ChatRoom, Message
from accounts.models import User
from products.models import Product


class ChatRoomListView(LoginRequiredMixin, ListView):
    """แสดงรายการห้องแชททั้งหมดของ user"""
    model = ChatRoom
    template_name = 'chats/room_list.html'
    context_object_name = 'rooms'

    def get_queryset(self):
        return ChatRoom.objects.filter(
            participants=self.request.user
        ).annotate(
            last_message_time=Max('messages__created_at')
        ).order_by('-last_message_time')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add computed fields for each room
        rooms_with_data = []
        for room in context['rooms']:
            room.other_user = room.get_other_participant(self.request.user)
            room.unread_count = room.get_unread_count(self.request.user)
            room.last_message = room.get_last_message()
            rooms_with_data.append(room)
        context['rooms'] = rooms_with_data
        return context


class ChatRoomView(LoginRequiredMixin, DetailView):
    """หน้าห้องแชท"""
    model = ChatRoom
    template_name = 'chats/room.html'
    context_object_name = 'room'
    pk_url_kwarg = 'room_id'

    def get_queryset(self):
        # Only allow access to rooms the user is a participant of
        return ChatRoom.objects.filter(participants=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = self.object
        
        # Mark all messages as read
        room.messages.filter(is_read=False).exclude(sender=self.request.user).update(is_read=True)
        
        # Get messages - use 'chat_messages' to avoid conflict with Django flash messages
        context['chat_messages'] = room.messages.select_related('sender').all()
        context['other_user'] = room.get_other_participant(self.request.user)
        return context


class StartChatView(LoginRequiredMixin, View):
    """Start a chat with another user"""
    
    def get(self, request, user_id):
        other_user = get_object_or_404(User, id=user_id)
        
        # Don't allow chatting with yourself
        if other_user == request.user:
            return redirect('chats:room_list')
        
        # Find existing room or create new one
        room = ChatRoom.objects.filter(
            participants=request.user
        ).filter(
            participants=other_user
        ).first()
        
        if not room:
            room = ChatRoom.objects.create()
            room.participants.add(request.user, other_user)
        
        return redirect('chats:room', room_id=room.id)


class StartProductChatView(LoginRequiredMixin, View):
    """Start a chat about a specific product (with optional first message)"""
    
    def get_or_create_room(self, request, product):
        """Get existing room or create new one"""
        seller = product.seller
        
        # Find existing room for this product or create new one
        room = ChatRoom.objects.filter(
            participants=request.user
        ).filter(
            participants=seller
        ).filter(
            product=product
        ).first()
        
        if not room:
            room = ChatRoom.objects.create(product=product)
            room.participants.add(request.user, seller)
        
        return room
    
    def get(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        
        # Don't allow chatting with yourself
        if product.seller == request.user:
            return redirect('products:detail', pk=product_id)
        
        room = self.get_or_create_room(request, product)
        return redirect('chats:room', room_id=room.id)
    
    def post(self, request, product_id):
        """Start chat with first message from product page"""
        product = get_object_or_404(Product, id=product_id)
        
        # Don't allow chatting with yourself
        if product.seller == request.user:
            return redirect('products:detail', pk=product_id)
        
        room = self.get_or_create_room(request, product)
        
        # Create first message if provided
        message_content = request.POST.get('message', '').strip()
        if message_content:
            Message.objects.create(
                room=room,
                sender=request.user,
                content=message_content
            )
            # Update room's updated_at
            room.updated_at = timezone.now()
            room.save(update_fields=['updated_at'])
        
        return redirect('chats:room', room_id=room.id)


# ============ API Views for AJAX ============

class GetMessagesView(LoginRequiredMixin, View):
    """Get messages for a chat room (AJAX)"""
    
    def get(self, request, room_id):
        room = get_object_or_404(
            ChatRoom.objects.filter(participants=request.user),
            id=room_id
        )
        
        # Get messages after a certain ID if provided
        after = request.GET.get('after')
        messages = room.messages.select_related('sender')
        
        if after:
            try:
                after_msg = Message.objects.get(id=after)
                messages = messages.filter(created_at__gt=after_msg.created_at)
            except Message.DoesNotExist:
                pass
        
        messages_data = [{
            'id': str(msg.id),
            'sender_id': str(msg.sender.id),
            'sender_name': msg.sender.get_full_name_display(),
            'content': msg.content,
            'is_mine': msg.sender == request.user,
            'created_at': msg.created_at.isoformat(),
        } for msg in messages]
        
        return JsonResponse({'messages': messages_data})


class SendMessageView(LoginRequiredMixin, View):
    """Send a message (AJAX)"""
    
    def post(self, request, room_id):
        room = get_object_or_404(
            ChatRoom.objects.filter(participants=request.user),
            id=room_id
        )
        
        try:
            data = json.loads(request.body)
            content = data.get('content', '').strip()
        except json.JSONDecodeError:
            content = request.POST.get('content', '').strip()
        
        if not content:
            return JsonResponse({'error': 'Message content is required'}, status=400)
        
        message = Message.objects.create(
            room=room,
            sender=request.user,
            content=content
        )
        
        # Update room's updated_at
        room.updated_at = timezone.now()
        room.save(update_fields=['updated_at'])
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': str(message.id),
                'sender_id': str(message.sender.id),
                'sender_name': message.sender.get_full_name_display(),
                'content': message.content,
                'is_mine': True,
                'created_at': message.created_at.isoformat(),
            }
        })


class MarkReadView(LoginRequiredMixin, View):
    """Mark messages as read (AJAX)"""
    
    def post(self, request, room_id):
        room = get_object_or_404(
            ChatRoom.objects.filter(participants=request.user),
            id=room_id
        )
        
        # Mark all messages from others as read
        updated = room.messages.filter(
            is_read=False
        ).exclude(
            sender=request.user
        ).update(is_read=True)
        
        return JsonResponse({'success': True, 'marked_read': updated})

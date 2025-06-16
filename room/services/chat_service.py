from channels.db import database_sync_to_async
from room.models import ChatMessage
from django.utils import timezone

@database_sync_to_async
def save_chat_message(room_id, message, sender, is_system=False):
    """Save a chat message to the database."""
    try:
        chat_message = ChatMessage.objects.create(
            room_id=room_id,
            sender=sender,
            message=message,
            is_system=is_system
        )
        return chat_message
    except Exception as e:
        print(f"[ERROR] Failed to save chat message: {str(e)}")
        return None

@database_sync_to_async
def clear_chat_messages(room_id):
    """Clear all chat messages for a room."""
    try:
        ChatMessage.objects.filter(room_id=room_id).delete()
    except Exception as e:
        print(f"[ERROR] Failed to clear chat messages: {str(e)}")

@database_sync_to_async
def get_chat_history(room_id):
    """Retrieve the chat history for a room."""
    try:
        messages = ChatMessage.objects.filter(room_id=room_id).order_by('timestamp')[:100]
        return [
            {
                'message': msg.message,
                'sender': msg.sender,
                'timestamp': msg.timestamp.strftime('%I:%M %p'),
                'is_system': msg.is_system
            } for msg in messages
        ]
    except Exception as e:
        print(f"[ERROR] Failed to fetch chat history: {str(e)}")
        return []
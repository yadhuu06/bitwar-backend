from channels.db import database_sync_to_async
from room.models import Room, RoomParticipant
from django.core.exceptions import ObjectDoesNotExist

@database_sync_to_async
def get_room(room_id):
    """
    Retrieve a room by its ID with related active_question.
    
    Args:
        room_id (str): The ID of the room to retrieve.
    
    Returns:
        Room: The Room model instance, or None if not found.
    """
    try:
        return Room.objects.select_related('active_question').get(room_id=room_id)
    except Room.DoesNotExist:
        return None

@database_sync_to_async
def get_room_list():
    """
    Retrieve a list of active rooms with their participants.
    
    Returns:
        list: A list of dictionaries containing room details and participants.
    """
    try:
        rooms = Room.objects.filter(is_active=True).prefetch_related('participants').values(
            'room_id', 'name', 'owner__username', 'topic', 'difficulty',
            'time_limit', 'capacity', 'participant_count', 'visibility', 'status', 'is_ranked', 'join_code'
        )
        processed_rooms = []
        for room in rooms:
            participants = list(RoomParticipant.objects.filter(room_id=room['room_id']).values(
                'user__username', 'role', 'status', 'ready'
            ))
            processed_rooms.append({
                **room,
                'room_id': str(room['room_id']),
                'participants': participants
            })
        return processed_rooms
    except Exception as e:
        print(f"[ERROR] Failed to fetch room list: {str(e)}")
        return []

@database_sync_to_async
def close_room(room_id):
    """
    Close a room by setting is_active to False and status to 'closed'.
    
    Args:
        room_id (str): The ID of the room to close.
    
    Returns:
        bool: True if the room was closed successfully, False otherwise.
    """
    try:
        room = Room.objects.get(room_id=room_id)
        room.is_active = False
        room.status = 'closed'
        room.save()
        return True
    except Room.DoesNotExist:
        return False
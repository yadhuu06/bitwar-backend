from channels.db import database_sync_to_async
from room.models import Room, RoomParticipant

@database_sync_to_async
def get_room(room_id):
    """Retrieve a room by ID."""
    try:
        return Room.objects.get(room_id=room_id)
    except Room.DoesNotExist:
        return None

@database_sync_to_async
def get_room_list():
    """Retrieve the list of active rooms with participants."""
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

@database_sync_to_async
def close_room(room_id):
    """Close a room and mark it inactive."""
    try:
        room = Room.objects.get(room_id=room_id)
        room.is_active = False
        room.status = 'closed'
        room.save()
    except Room.DoesNotExist:
        print(f"[ERROR] Room {room_id} not found")
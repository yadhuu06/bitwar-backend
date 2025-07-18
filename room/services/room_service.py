from channels.db import database_sync_to_async
from room.models import Room, RoomParticipant
from django.core.exceptions import ObjectDoesNotExist
from battle.tasks import cleanup_room_data
@database_sync_to_async
def get_room(room_id):

    try:
        return Room.objects.select_related('active_question').get(room_id=room_id)
    except Room.DoesNotExist:
        return None

@database_sync_to_async
def get_room_list():

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

    try:
        room = Room.objects.get(room_id=room_id)
        room.is_active = False
        room.status = 'closed'
        room.save()
        cleanup_room_data.apply_async((room.room_id,), countdown=120)
        return True
    except Room.DoesNotExist:
        return False
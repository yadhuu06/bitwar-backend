from channels.db import database_sync_to_async
from room.models import Room, RoomParticipant
from django.utils import timezone

@database_sync_to_async
def check_participant(user, room_id):
    """Check if a user is a participant in a room and not kicked."""
    return RoomParticipant.objects.filter(
        user=user,
        room_id=room_id
    ).exclude(status='kicked').exists()

@database_sync_to_async
def get_participants(room_id):
    """Retrieve all participants in a room."""
    return list(RoomParticipant.objects.filter(room_id=room_id).values(
        'user__username', 'role', 'status', 'ready'
    ))

@database_sync_to_async
def ensure_participant(room_id, user, status):
    """Ensure a participant exists in a room, creating or updating as needed."""
    try:
        room = Room.objects.get(room_id=room_id)
        participant, created = RoomParticipant.objects.get_or_create(
            room_id=room_id,
            user=user,
            defaults={
                'role': 'host' if room.owner == user else 'participant',
                'status': status,
                'joined_at': timezone.now(),
                'ready': False,
            }
        )
        if not created:
            participant.status = status
            participant.left_at = None if status == 'joined' else timezone.now()
            participant.save()

        room.participant_count = RoomParticipant.objects.filter(
            room_id=room_id, status='joined'
        ).count()
        room.save()

        return participant
    except Room.DoesNotExist:
        print(f"[ERROR] Room {room_id} not found")
        return None

@database_sync_to_async
def update_participant_status(room_id, user, status):
    """Update the status of a participant in a room."""
    try:
        participant = RoomParticipant.objects.get(room_id=room_id, user=user)
        participant.status = status
        participant.left_at = None if status == 'joined' else timezone.now()
        participant.save()

        room = Room.objects.get(room_id=room_id)
        room.participant_count = RoomParticipant.objects.filter(
            room_id=room_id, status='joined'
        ).count()
        room.save()

        return list(RoomParticipant.objects.filter(room_id=room_id).values(
            'user__username', 'role', 'status', 'ready'
        ))
    except RoomParticipant.DoesNotExist:
        print(f"[ERROR] Participant {user} not found in room {room_id}")
        return None
    except Room.DoesNotExist:
        print(f"[ERROR] Room {room_id} not found")
        return None

@database_sync_to_async
def update_ready_status(room_id, user, ready):
    """Update the ready status of a participant."""
    try:
        participant = RoomParticipant.objects.get(room_id=room_id, user=user)
        participant.ready = ready
        participant.ready_at = timezone.now() if ready else None
        participant.save()
    except RoomParticipant.DoesNotExist:
        print(f"[ERROR] Participant {user} not found for ready status update")

@database_sync_to_async
def kick_participant(room_id, target_username):
    """Kick a participant from a room."""
    try:
        participant = RoomParticipant.objects.get(
            room_id=room_id,
            user__username=target_username,
            status='joined'
        )
        participant.status = 'kicked'
        participant.left_at = timezone.now()
        participant.blocked = True
        participant.save()

        room = Room.objects.get(room_id=room_id)
        room.participant_count = RoomParticipant.objects.filter(
            room_id=room_id, status='joined'
        ).count()
        room.save()

        return True
    except RoomParticipant.DoesNotExist:
        print(f"[ERROR] Cannot kick {target_username}: Participant not found")
        return False
    except Room.DoesNotExist:
        print(f"[ERROR] Room {room_id} not found")
        return False
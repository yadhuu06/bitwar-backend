from celery import shared_task
from .models import BattleResult
from room.models import Room, RoomParticipant, ChatMessage
from django.db import transaction
from datetime import timedelta
from django.utils import timezone
from itertools import chain
import logging

logger = logging.getLogger(__name__)
"""
Celery task to handle the cleanup of all database records related to a room 
after it has either ended (status: 'completed') or been forcefully closed 
(status: 'closed').

This includes:
- Deleting all RoomParticipant entries linked to the room
- Deleting all ChatMessage entries (based on string room_id)
- Deleting related BattleResult entries (only if the room was completed)
- Deleting the Room itself

The task is designed to run asynchronously with a delay ( 5 minutes),
ensuring no immediate abrupt data removal for user-side transitions.
"""


@shared_task
def cleanup_room_data(room_id):
    try:
        with transaction.atomic():
            room = Room.objects.get(room_id=room_id)

            
            
            RoomParticipant.objects.filter(room=room).delete()

            ChatMessage.objects.filter(room_id=str(room_id)).delete()

            if room.status == "Completed":
                BattleResult.objects.filter(room=room).delete()

            room.delete()  

            return f"[CLEANED] Room {room_id} and related data cleaned successfully."

    except Room.DoesNotExist:
        return f"[ERROR] Room with ID {room_id} does not exist."
    

@shared_task
def cleanup_inactive_rooms():
    now = timezone.now()

    inactive_rooms = Room.objects.filter(
        status__in=['active', 'Playing','completed'],
        start_time__isnull=True,
        created_at__lte=now - timedelta(hours=1)
    )


    stale_rooms = Room.objects.filter(
        status__in=['active', 'Playing','Completed'],
        start_time__isnull=False,
        start_time__lte=now - timedelta(minutes=65)
    )

    rooms_to_cleanup = inactive_rooms.union(stale_rooms)
    cleaned_count = rooms_to_cleanup.count()

    for room in rooms_to_cleanup:
        cleanup_room_data.delay(str(room.room_id))  

    return f'[CLEANUP-TASK] {cleaned_count} inactive/long-running rooms scheduled for cleanup.'

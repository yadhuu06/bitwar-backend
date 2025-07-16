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

            if room.status not in ["completed", "closed"]:
                return f"[SKIPPED] Room {room_id} is not completed or closed."
            
            RoomParticipant.objects.filter(room=room).delete()

            ChatMessage.objects.filter(room_id=str(room_id)).delete()

            if room.status == "completed":
                BattleResult.objects.filter(room=room).delete()

            room.delete()  

            return f"[CLEANED] Room {room_id} and related data cleaned successfully."

    except Room.DoesNotExist:
        return f"[ERROR] Room with ID {room_id} does not exist."
    

@shared_task
def cleanup_inactive_rooms():
    now = timezone.now()

    created_rooms = Room.objects.filter(
        status='active',
        created_at__lte=now - timedelta(hours=1)
    )

    playing_rooms = Room.objects.filter(
        status='playing',
        start_time__lte=now - timedelta(minutes=65)
    )

    total_cleaned = 0
    for room in chain(created_rooms, playing_rooms):
        cleanup_room_data.delay(str(room.room_id))
        total_cleaned += 1

    logger.warning("Scheduled celery task triggered")
    logger.info(f"[CLEANUP-TASK] {total_cleaned} rooms scheduled for cleanup.")
    return f"[CLEANUP-TASK] {total_cleaned} inactive/long-running rooms scheduled for cleanup."
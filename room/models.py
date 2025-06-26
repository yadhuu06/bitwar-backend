from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync, sync_to_async
import uuid
import random
import string
import json
from problems.models import Question

def generate_join_code():
    characters = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choice(characters) for _ in range(8))  
        if not Room.objects.filter(join_code=code).exists():
            return code

class Room(models.Model):
    ROOM_VISIBILITY_CHOICES = (
        ('public', 'Public'),
        ('private', 'Private'),
    )

    DIFFICULTY_LEVELS = (
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    )

    room_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False, primary_key=True)
    join_code = models.CharField(max_length=8, unique=True, default=generate_join_code, editable=False)
    name = models.CharField(max_length=100, null=False, blank=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_rooms')
    topic = models.CharField(max_length=50, null=False, blank=False)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_LEVELS, null=False, blank=False)
    time_limit = models.PositiveIntegerField(help_text="Time limit in minutes", null=False, blank=False)
    is_ranked = models.BooleanField(default=True, null=False)
    capacity = models.PositiveIntegerField(default=2, null=False, blank=False)
    participant_count = models.PositiveIntegerField(default=1, null=False, blank=False)
    visibility = models.CharField(max_length=10, choices=ROOM_VISIBILITY_CHOICES, default='public', null=False, blank=False)
    password = models.CharField(max_length=128, blank=True, null=True)
    
    active_question = models.ForeignKey(Question, null=True, blank=True, on_delete=models.SET_NULL)

    is_active = models.BooleanField(default=True, null=False)
    status = models.CharField(
        max_length=20,
        choices=(('active', 'Active'), ('completed', 'Completed'), ('archived', 'Archived')),
        default='active',
        null=False,
        blank=False
    )
    created_at = models.DateTimeField(auto_now_add=True)
    start_time = models.DateTimeField(null=True, blank=True, help_text="Time when the battle started")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['join_code']),
            models.Index(fields=['owner']),
            models.Index(fields=['visibility']),
            models.Index(fields=['status']),
        ]
        ordering = ['-created_at']

    def is_full(self):
        return self.participant_count >= self.capacity

    def clean(self):
        if self.visibility == 'private' and not self.password:
            raise models.ValidationError({'password': 'Password is required for private rooms.'})

    def __str__(self):
        return f"Room {self.name} (Join Code: {self.join_code})"

class RoomParticipant(models.Model):
    ROLE_CHOICES = (
        ('host', 'Host'),
        ('participant', 'Participant'),
    )

    STATUS_CHOICES = (
        ('waiting', 'Waiting'),
        ('joined', 'Joined'),
        ('left', 'Left'),
        ('kicked', 'Kicked'),
    )

    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='room_participations'
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='participant', null=False, blank=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting', null=False, blank=False)
    ready = models.BooleanField(default=False, null=False)
    ready_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    blocked = models.BooleanField(default=False)



    class Meta:
        unique_together = ('room', 'user')
        indexes = [
            models.Index(fields=['room', 'status']),
            models.Index(fields=['room', 'user']),
            models.Index(fields=['status']),
        ]
        ordering = ['joined_at']

    def save(self, *args, **kwargs):
        if self.ready and not self.ready_at:
            self.ready_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} in {self.room.name} as {self.role} ({self.status})"

@sync_to_async
def get_room_list():
    rooms = Room.objects.filter(is_active=True).values(
        'room_id', 'name', 'owner__username', 'topic', 'difficulty',
        'time_limit', 'capacity', 'participant_count', 'visibility', 'status'
    )
    return [
        {**room, 'room_id': str(room['room_id'])} for room in rooms
    ]

@receiver(post_save, sender=Room)
@receiver(post_save, sender=RoomParticipant)
def broadcast_room_update(sender, instance, **kwargs):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'rooms',
        {
            'type': 'room_update',
            'rooms': async_to_sync(get_room_list)() 
        }
    )


class ChatMessage(models.Model):
    room_id = models.CharField(max_length=50)
    sender = models.CharField(max_length=100)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_system = models.BooleanField(default=False)


    class Meta:
        indexes = [
            models.Index(fields=['room_id', 'timestamp']),
        ]
        ordering = ['timestamp']
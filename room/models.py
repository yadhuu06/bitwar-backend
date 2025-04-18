from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


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

    room_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=100, unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_rooms')
    topic = models.CharField(max_length=100)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_LEVELS)
    time_limit = models.PositiveIntegerField(help_text="Time limit in minutes")
    capacity = models.PositiveIntegerField(default=2)
    visibility = models.CharField(max_length=10, choices=ROOM_VISIBILITY_CHOICES, default='public')
    password = models.CharField(max_length=128, blank=True, null=True)  # Can hash this if needed
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_full(self):
        return self.participants.count() >= self.capacity

    def __str__(self):
        return f"Room {self.name} ({self.room_id})"



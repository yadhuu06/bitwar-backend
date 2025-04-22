from django.db import models
from django.conf import settings
from django.utils import timezone
import random
import uuid

def generate_unique_code():
    
    while True:
        code = random.randint(10000, 99999)  
        if not Room.objects.filter(room_id=code).exists():
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

    room_id = models.IntegerField(unique=True, default=generate_unique_code, editable=False)
    name = models.CharField(max_length=100, null=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_rooms')
    topic = models.CharField(max_length=50)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_LEVELS)
    time_limit = models.PositiveIntegerField(help_text="Time limit in minutes")
    capacity = models.PositiveIntegerField(default=2)
    visibility = models.CharField(max_length=10, choices=ROOM_VISIBILITY_CHOICES, default='public')
    password = models.CharField(max_length=128, blank=True, null=True)  
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_full(self):
        return self.participants.count() >= self.capacity
   

    def __str__(self):
        return f"Room {self.name} ({self.room_id})"

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
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='participant')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    ready = models.BooleanField(default=False) 
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('room', 'user')
        indexes = [
            models.Index(fields=['room', 'status']),
            models.Index(fields=['room', 'user']),
        ]
        ordering = ['joined_at']

    def __str__(self):
        return f"{self.user.username} in {self.room.name} as {self.role} ({self.status})"

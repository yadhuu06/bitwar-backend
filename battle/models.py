from django.db import models
from django.contrib.auth import get_user_model
import uuid
from django.db.models import JSONField

User = get_user_model()

class BattleResult(models.Model):
    battle_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    room = models.ForeignKey('room.Room', on_delete=models.CASCADE, related_name='results')
    question = models.ForeignKey('problems.Question', on_delete=models.CASCADE, related_name='battle_results')
    results = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['battle_id']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"BattleResult for Room {self.room.name} - Question {self.question.title}"

    def add_participant_result(self, user, position, completion_time):
        """Add or update a participant's result in the JSONField."""
        existing_results = self.results
        participant_result = {
            'username': user.username,
            'position': position,
            'completion_time': completion_time.isoformat() if completion_time else None,
        }
        existing_results.append(participant_result)
        self.results = existing_results
        self.save()

class UserRanking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='battle_rankings')
    points = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['points']),
        ]
        ordering = ['-points']

    def __str__(self):
        return f"{self.user.username}: {self.points} points"
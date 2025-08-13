from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class Season(models.Model):
    name = models.CharField(max_length=100, unique=True)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Ranking(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='rankings'
    )
    rating = models.FloatField(default=1200)
    total_matches = models.PositiveIntegerField(default=0)
    wins = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)
    season = models.ForeignKey(
        Season,
        on_delete=models.CASCADE,
        related_name='season_rankings'
    )

    class Meta:
        unique_together = ('user', 'season')
        ordering = ['-rating']

    def __str__(self):
        return f"{self.user} - {self.rating}"

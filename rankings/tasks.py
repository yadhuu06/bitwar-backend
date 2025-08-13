from celery import shared_task
from django.utils import timezone
from .models import Season

@shared_task
def check_and_create_new_season():
    now = timezone.now()

    # Check if there's an active season
    active_season = Season.objects.filter(is_active=True).first()

    if active_season:
        # If the season is over, close it and start a new one
        season_duration_days = 30  # or 45, or from settings
        if (now - active_season.start_date).days >= season_duration_days:
            active_season.is_active = False
            active_season.end_date = now
            active_season.save()

            # Create the new season
            new_season_number = Season.objects.count() + 1
            Season.objects.create(
                name=f"Season {new_season_number}",
                start_date=now,
                is_active=True
            )
    else:
        # If no season exists, create the first one
        Season.objects.create(
            name="Season 1",
            start_date=now,
            is_active=True
        )

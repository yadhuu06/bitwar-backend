from django.db import transaction
from .models import Ranking, Season
from django.conf import settings
from math import pow
from authentication.models import CustomUser
from room.models import Room
def calculate_elo_1v1(room_id, winner_id):
     

    room = Room.objects.get(room_id=room_id)
    participants = list(room.participants.all())

    if len(participants) != 2:
        raise ValueError("1v1 room must have exactly 2 participants.")

    # Get winner and loser as real user objects
    winner = CustomUser.objects.get(user_id=winner_id)
    loser = [p for p in participants if p.user.user_id != winner_id][0].user

    # Get current season
    season = Season.objects.filter(is_active=True).first()
    if not season:
        raise ValueError("No active season found.")

    winner_rank, _ = Ranking.objects.get_or_create(user=winner, season=season)
    loser_rank, _ = Ranking.objects.get_or_create(user=loser, season=season)

    K = 32
    expected_winner = 1 / (1 + pow(10, (loser_rank.rating - winner_rank.rating) / 400))
    expected_loser = 1 / (1 + pow(10, (winner_rank.rating - loser_rank.rating) / 400))

    with transaction.atomic():
        winner_rank.rating += K * (1 - expected_winner)
        loser_rank.rating += K * (0 - expected_loser)
        winner_rank.wins += 1
        loser_rank.losses += 1
        winner_rank.total_match += 1
        loser_rank.total_match += 1
        winner_rank.save()
        loser_rank.save()


def calculate_elo_squad(battle):
    """
    Updates the ratings for all participants in a squad battle using an
    Elo-like rating system adapted for multiple players.

    Args:
        battle: A Battle instance containing multiple participants (3 to 5 players).
    """
    
    # Convert participants QuerySet to a list for easy iteration
    participants = list(battle.participants.all())

    # K-factor: determines how much the rating changes after a game
    k_factor = 32  

    # Loop through each participant to update their rating
    for player in participants:
        # Get this player's ranking for the current season
        player_rank = Ranking.objects.get(user=player.user, season=battle.season)

        # -------------------------------

        # Expected score is based on comparing this player to every other opponent
        expected = 0
        for opponent in participants:
            if opponent == player:
                continue  # Don't compare a player to themselves

            opponent_rank = Ranking.objects.get(user=opponent.user, season=battle.season)

            # Elo formula for expected score vs this opponent
            expected += 1 / (1 + 10 ** ((opponent_rank.rating - player_rank.rating) / 400))

        # Average the expected score over all opponents
        expected /= (len(participants) - 1)

        # ------------------------------

        # Position → score between 0 and 1
        # Example: if there are 4 players, position 1 gets 1.0, position 4 gets 0.0
        actual = (len(participants) - player.position) / (len(participants) - 1)

        # ------------------------------

        player_rank.rating += k_factor * (actual - expected)
        player_rank.total_matches += 1

        # Track wins/losses for stats
        if player.position == 1:
            player_rank.wins += 1
        else:
            player_rank.losses += 1

        # Save updated ranking
        player_rank.save()


def calculate_elo_team(battle):
    """
    Update ratings for a team-based battle using the Elo rating system.

    Steps:
    1. Calculate average rating for each team.
    2. Compare each team against all others to get expected score.
    3. Update each member's rating based on the team's actual result.
    """

    k_factor = 32  # Controls rating change speed

    # Step 1: Group participants by team
    teams = {}  # {team_id: [participants]}
    for participant in battle.participants.all():
        teams.setdefault(participant.team_id, []).append(participant)

    # Step 2: Calculate average rating for each team
    team_ratings = {}
    for team_id, members in teams.items():
        total_rating = 0
        for member in members:
            member_rank = Ranking.objects.get(user=member.user, season=battle.season)
            total_rating += member_rank.rating
        team_ratings[team_id] = total_rating / len(members)  # average rating

    # Step 3: Update ratings for each team
    for team_id, members in teams.items():
        team_rating = team_ratings[team_id]

        # Calculate expected score vs all other teams
        expected = 0
        for opp_team_id, opp_members in teams.items():
            if opp_team_id == team_id:
                continue
            opp_rating = team_ratings[opp_team_id]
            expected += 1 / (1 + 10 ** ((opp_rating - team_rating) / 400))

        expected /= (len(teams) - 1)  # Average expectation

        # Actual score (1 = win, 0 = loss, 0.5 = draw)
        # Here, position=1 means first place
        team_position = members[0].team_position  # Same for all team members
        actual = (len(teams) - team_position) / (len(teams) - 1)

        # Step 4: Update each member's rating
        for member in members:
            member_rank = Ranking.objects.get(user=member.user, season=battle.season)
            member_rank.rating += k_factor * (actual - expected)
            member_rank.total_matches += 1

            if team_position == 1:
                member_rank.wins += 1
            else:
                member_rank.losses += 1

            member_rank.save()

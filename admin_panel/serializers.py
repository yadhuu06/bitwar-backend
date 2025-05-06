from rest_framework import serializers
from authentication.models import CustomUser
from room.models import Room, RoomParticipant
from authentication.models import CustomUser
class UserSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source='user_id', read_only=True)

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'is_blocked']
class RoomParticipantSerializer(serializers.ModelSerializer):
    user__username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = RoomParticipant
        fields = ['user__username', 'role']

class RoomSerializer(serializers.ModelSerializer):
    owner__username = serializers.CharField(source='owner.username', read_only=True)
    participant_count = serializers.IntegerField(read_only=True)
    participants = RoomParticipantSerializer(many=True, read_only=True)

    class Meta:
        model = Room
        fields = [
            'room_id', 'name', 'owner__username', 'visibility', 'join_code',
            'difficulty', 'time_limit', 'capacity', 'participant_count',
            'status', 'topic', 'participants'
        ]
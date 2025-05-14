from rest_framework import serializers
from .models import Room

class RoomCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ['name', 'topic', 'difficulty', 'time_limit', 'capacity', 'visibility', 'password','is_ranked']

    def validate(self, data):
        if data.get('visibility') == 'private' and not data.get('password'):
            raise serializers.ValidationError({'password': 'Password is required for private rooms.'})
        if not data.get('is_ranked') and (not data.get('time_limit') or data.get('time_limit') <= 0):
            raise serializers.ValidationError({'time_limit': 'Time limit must be positive for non-ranked rooms.'})
        if data.get('capacity') < 2:
            raise serializers.ValidationError({'capacity': 'Capacity must be at least 2.'})
        return data
# rooms/serializers.py
from rest_framework import serializers
from .models import Room

class RoomCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = [
            'name', 'topic', 'difficulty', 'time_limit', 'capacity',
            'visibility', 'password'
        ]

    def create(self, validated_data):
        request = self.context['request']
        return Room.objects.create(owner=request.user, **validated_data)

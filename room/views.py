from django.shortcuts import render
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from .models import Room, RoomParticipant
from .serializers import RoomCreateSerializer
import json


def room_view(request):
    print("call coming")


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_room(request):
    try:
        data = json.loads(request.body.decode('utf-8'))


        topic = data.get('topic')
        difficulty = data.get('difficulty')
        time_limit = data.get('time_limit')
        capacity = data.get('capacity', 2)
        visibility = data.get('visibility', 'public')
        password = data.get('password', '')

        if not all([topic, difficulty, time_limit]):
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)

        room_name = request.user.username

        room = Room.objects.create(
            name=room_name,
            topic=topic,
            difficulty=difficulty,
            time_limit=time_limit,
            capacity=capacity,
            visibility=visibility,
            password=password if visibility == 'private' else '',
            owner=request.user,
        )

        RoomParticipant.objects.create(
            room=room,
            user=request.user,
            role='host',
            status='joined',
            ready=False,
        )

        return Response({
            'message': 'Room created successfully',
            'room_id': str(room.room_id),
            'room_name': room.name
        }, status=status.HTTP_201_CREATED)

    except json.JSONDecodeError:
        return Response({'error': 'Invalid JSON'}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
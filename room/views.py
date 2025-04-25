from django.shortcuts import render
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes

from .serializers import RoomCreateSerializer
import json
from django.http import JsonResponse


def room_view(request):
    print("hai")
 
import json
import traceback
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Room, RoomParticipant
from django.utils import timezone

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_room(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        print("the data is ", data)

        # Validate required fields
        required_fields = ['name', 'topic', 'difficulty', 'time_limit']
        if not all(data.get(field) for field in required_fields):
            print("Missing required fields")
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)

        room_name = data.get('name')
        topic = data.get('topic')
        difficulty = data.get('difficulty')
        time_limit = data.get('time_limit')
        print(type(time_limit))
        capacity = data.get('capacity', 2)
        visibility = data.get('visibility', 'public')
        password = data.get('password', '') if visibility == 'private' else ''

        print("Authenticated user:", request.user)
        print("creating room")
        room = Room.objects.create(
            name=room_name,
            topic=topic,
            difficulty=difficulty,
            time_limit=time_limit,
            capacity=capacity,
            visibility=visibility,
            password=password,
            owner=request.user,
        )
        print("created room")

        print("creating participants")
        # Check for existing participant
        if RoomParticipant.objects.filter(room=room, user=request.user).exists():
            print("Participant already exists for this room and user")
            return Response({'error': 'User is already a participant in this room'}, status=status.HTTP_400_BAD_REQUEST)

        participant = RoomParticipant.objects.create(
            room=room,
            user=request.user,
            role='host',
            status='joined',
            ready=False,
        )
        print("created participant")

        return Response({
            'message': 'Room created successfully',
            'room_id': str(room.room_id),
            'room_name': room.name
        }, status=status.HTTP_201_CREATED)

    except json.JSONDecodeError:
        return Response({'error': 'Invalid JSON'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        print("Error creating room:", str(e))
        print(traceback.format_exc())
        return Response({'error': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
import json
import traceback
from .models import Room, RoomParticipant
from .serializers import RoomCreateSerializer
from django.db.models import F


from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Room, RoomParticipant
from .serializers import RoomCreateSerializer
import json

def room_view(request):
    if request.method == 'GET':
        rooms = Room.objects.filter(is_active=True).values(
            'room_id', 'name', 'owner__username', 'topic', 'difficulty',
            'time_limit', 'capacity', 'participant_count', 'visibility', 'status'
        )
        return Response({'rooms': list(rooms)}, status=status.HTTP_200_OK)
    return Response({'error': 'Invalid request method'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_room(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        serializer = RoomCreateSerializer(data=data)
        if not serializer.is_valid():
            return Response({'error': 'Invalid input', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        room = Room.objects.create(
            name=serializer.validated_data['name'],
            topic=serializer.validated_data['topic'],
            difficulty=serializer.validated_data['difficulty'],
            time_limit=serializer.validated_data['time_limit'],
            capacity=serializer.validated_data.get('capacity', 2),
            visibility=serializer.validated_data.get('visibility', 'public'),
            password=serializer.validated_data.get('password', ''),
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
            'room_name': room.name,
            'join_code': room.join_code,
            'owner': request.user.username,
        }, status=status.HTTP_201_CREATED)
    except json.JSONDecodeError:
        return Response({'error': 'Invalid JSON'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
def join_room_view(request, room_id):
    if request.method == 'POST':
        try:
            if not request.user.is_authenticated:
                return JsonResponse({'error': 'Authentication required'}, status=401)

            room = Room.objects.get(room_id=room_id)
            if room.is_full():
                return JsonResponse({'error': 'Room is full'}, status=400)


            RoomParticipant.objects.get_or_create(
                room=room,
                user=request.user,
                defaults={'role': 'participant', 'status': 'joined'}
            )


            room.participant_count = F('participant_count') + 1
            room.save()
            room.refresh_from_db()

            return JsonResponse({'status': 'success', 'message': 'Joined room'}, status=200)
        except Room.DoesNotExist:
            return JsonResponse({'error': 'Room not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=405)
from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Room, RoomParticipant
from .serializers import RoomCreateSerializer
from django.db.models import F
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import traceback
@api_view(['GET'])
def room_view(request):
    try:
        rooms = Room.objects.filter(is_active=True).values(
            'room_id', 'name', 'owner__username', 'topic', 'difficulty',
            'time_limit', 'capacity', 'participant_count', 'visibility', 'status','join_code'
        )
        
        return Response({'rooms': list(rooms)}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': f'Failed to fetch rooms: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_room(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        serializer = RoomCreateSerializer(data=data)
        if not serializer.is_valid():
            print("Serializer is not valid:", serializer.errors)
            return Response({'error': 'Invalid input', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        validated_data = serializer.validated_data
        password = validated_data.get('password', '') if validated_data.get('visibility') != 'public' else ''
        print("my pass is ",password)
        print("room creating ")
        print("Authenticated User:", request.user)
        print("Is Authenticated:", request.user.is_authenticated)


        try:    room = Room.objects.create(
                name=serializer.validated_data['name'],
                topic=serializer.validated_data['topic'],
                difficulty=serializer.validated_data['difficulty'],
                time_limit=serializer.validated_data['time_limit'],
                capacity=serializer.validated_data.get('capacity', 2),
                visibility=serializer.validated_data.get('visibility', 'public'),
                password=password,
                owner=request.user,
            )
        except Exception as e:
            print("Room creation failed:", str(e))
            traceback.print_exc()
            return Response({'error': 'Room creation failed', 'details': str(e)}, status=500)


        try:
            print("i am trying to create participant")
            RoomParticipant.objects.create(
            room=room,
            user=request.user,
            role='host',
            status='joined',
            ready=False,
        )
        except Exception as e:
            print("participant creation failed")
            traceback.print_exc()
            print(f"room creation failed: {str(e)}")
            return Response({'error': f'Failed to create participant: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Broadcast room creation via Channels
        channel_layer = get_channel_layer()
        print("channel leyer",channel_layer)
        async_to_sync(channel_layer.group_send)(
            'rooms',
            {
                'type': 'room_update',
                'rooms': [{
                    'room_id': str(room.room_id),
                    'name': room.name,
                    'owner__username': room.owner.username,
                    'topic': room.topic,
                    'difficulty': room.difficulty,
                    'time_limit': room.time_limit,
                    'capacity': room.capacity,
                    'participant_count': room.participant_count,
                    'visibility': room.visibility,
                    'status': room.status,
                }]
            }
        )
        print("done")

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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def join_room_view(request, room_id):
    try:
        # Fetch room
        room = Room.objects.select_related('owner').get(room_id=room_id)


        # Check if user already a participant
        participant = RoomParticipant.objects.filter(room=room, user=request.user).first()

        if participant:
            if participant.blocked:
                return Response({'status': 'blocked', 'message': 'User is blocked from this room'}, status=status.HTTP_403_FORBIDDEN)

            return Response({
                'status': 'success',
                'message': 'Already joined',
                'role': participant.role,
                'room': {
                    'room_id': str(room.room_id),
                    'name': room.name,
                    'owner': room.owner.username,
                    'topic': room.topic,
                    'difficulty': room.difficulty,
                    'time_limit': room.time_limit,
                    'capacity': room.capacity,
                    'participant_count': room.participant_count,
                    'visibility': room.visibility,
                    'status': room.status,
                }
            }, status=status.HTTP_200_OK)

        # Check if room is full
        if room.is_full():
            return Response({'error': 'Room is full'}, status=status.HTTP_400_BAD_REQUEST)

        # Handle password if private room
        if room.visibility == 'private':
            password = request.data.get('password')
            if not password or room.password != password:
                return Response({'error': 'Invalid password'}, status=status.HTTP_403_FORBIDDEN)

        # Add participant
        new_participant, created = RoomParticipant.objects.get_or_create(
            room=room,
            user=request.user,
            defaults={'role': 'participant', 'status': 'joined'}
        )

        if created:
            room.participant_count = F('participant_count') + 1
            room.save()
            room.refresh_from_db()

        # Notify via channels
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'rooms',
            {
                'type': 'room_update',
                'rooms': [{
                    'room_id': str(room.room_id),
                    'name': room.name,
                    'owner__username': room.owner.username,
                    'topic': room.topic,
                    'difficulty': room.difficulty,
                    'time_limit': room.time_limit,
                    'capacity': room.capacity,
                    'participant_count': room.participant_count,
                    'visibility': room.visibility,
                    'status': room.status,
                }]
            }
        )

        return Response({
            'status': 'success',
            'message': 'Joined room',
            'role': new_participant.role,
            'room': {
                'room_id': str(room.room_id),
                'name': room.name,
                'owner': room.owner.username,
                'topic': room.topic,
                'difficulty': room.difficulty,
                'time_limit': room.time_limit,
                'capacity': room.capacity,
                'participant_count': room.participant_count,
                'visibility': room.visibility,
                'status': room.status,
            }
        }, status=status.HTTP_200_OK)

    except Room.DoesNotExist:
        return Response({'error': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

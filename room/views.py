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
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import Room
from problems.models import Question,Example,TestCase
import random
import logging


logger = logging.getLogger(__name__)

@api_view(['GET'])
def room_view(request):
    try:
        rooms = Room.objects.filter(is_active=True).values(
            'room_id', 'name', 'owner__username', 'topic', 'difficulty',
            'time_limit', 'capacity', 'participant_count', 'visibility', 'status', 'join_code', 'is_ranked'
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

        try:
            room = Room.objects.create(
                name=serializer.validated_data['name'],
                topic=serializer.validated_data['topic'].upper(),
                difficulty=serializer.validated_data['difficulty'].upper(),
                time_limit=serializer.validated_data.get('time_limit', 0),
                capacity=serializer.validated_data.get('capacity', 2),
                visibility=serializer.validated_data.get('visibility', 'public'),
                is_ranked=serializer.validated_data.get('is_ranked', False),
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
                    'is_ranked': room.is_ranked,
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
            'is_ranked': room.is_ranked
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({'error': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_room_details_view(request, room_id):
    try:
        room = Room.objects.select_related('owner').get(room_id=room_id)

        try:
            participant = RoomParticipant.objects.get(room=room, user=request.user)
            if participant.blocked:
                return Response({'error': 'You are not authorised person'}, status=status.HTTP_403_FORBIDDEN)
        except RoomParticipant.DoesNotExist:
            return Response({'error': 'You are not authorised person'}, status=status.HTTP_403_FORBIDDEN)

        participants = RoomParticipant.objects.filter(room=room).values('user__username', 'role', 'status', 'ready')

        return Response({
            'current_user': request.user.username,
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
                'join_code': room.join_code,
                'is_ranked': room.is_ranked
            },
            'participants': list(participants),
        }, status=status.HTTP_200_OK)

    except Room.DoesNotExist:
        return Response({'error': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def join_room_view(request, room_id):
    try:
        room = Room.objects.select_related('owner').get(room_id=room_id)
        participant = RoomParticipant.objects.filter(room=room, user=request.user).first()

        if participant:
            if participant.blocked:
                return Response({'status': 'blocked', 'message': 'User is blocked from this room'}, status=status.HTTP_403_FORBIDDEN)
            participant.status = 'joined'
            participant.left_at = None
            participant.save()
            print("User role:", participant.role)
            print("User status:", participant.status)

            participants = RoomParticipant.objects.filter(room=room).values('user__username', 'role', 'status', 'ready')
            print("passing the username", request.user.username)
            return Response({
                'status': 'success',
                'message': 'Already joined',
                'current_user': request.user.username,
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
                    'join_code': room.join_code,
                    'is_ranked': room.is_ranked
                },
                'participants': list(participants),
            }, status=status.HTTP_200_OK)

        if room.is_full():
            return Response({'error': 'Room is full'}, status=status.HTTP_400_BAD_REQUEST)
        if room.status.lower() != 'active':
            return Response({'error': 'Room is not currently active to join.'}, status=status.HTTP_403_FORBIDDEN)


        if room.visibility == 'private':
            password = request.data.get('password')
            if not password or room.password != password:
                return Response({'error': 'Invalid password'}, status=status.HTTP_403_FORBIDDEN)

        new_participant, created = RoomParticipant.objects.get_or_create(
            room=room,
            user=request.user,
            defaults={'role': 'participant', 'status': 'joined'}
        )

        if created:
            room.participant_count = F('participant_count') + 1
            room.save()
            room.refresh_from_db()

        channel_layer = get_channel_layer()
        participants = RoomParticipant.objects.filter(room=room).values('user__username', 'role', 'status', 'ready')
        async_to_sync(channel_layer.group_send)(
            f'room_{room_id}',
            {
                'type': 'participant_update',
                'participants': list(participants),
            }
        )
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
                    'join_code': room.join_code,
                    'is_ranked': room.is_ranked,
                }]
            }
        )

        return Response({
            'status': 'success',
            'message': 'Joined room',
            'current_user': request.user.username,
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
                'join_code': room.join_code,
                'is_ranked': room.is_ranked,
            },
            'participants': list(participants),
        }, status=status.HTTP_200_OK)
    except Room.DoesNotExist:
        return Response({'error': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def kick_participant_view(request, room_id):
    try:
        room = Room.objects.get(room_id=room_id)
        if not RoomParticipant.objects.filter(room=room, user=request.user, role='host').exists():
            return Response({'error': 'Only the host can kick participants'}, status=status.HTTP_403_FORBIDDEN)

        username = request.data.get('username')
        participant = RoomParticipant.objects.filter(room=room, user__username=username).first()
        if not participant:
            return Response({'error': 'Participant not found'}, status=status.HTTP_404_NOT_FOUND)

        participant.delete()
        room.participant_count = F('participant_count') - 1
        room.save()
        room.refresh_from_db()

        channel_layer = get_channel_layer()
        participants = RoomParticipant.objects.filter(room=room).values('user__username', 'role', 'status', 'ready')
        async_to_sync(channel_layer.group_send)(
            f'room_{room_id}',
            {
                'type': 'kicked',
                'username': username,
            }
        )
        async_to_sync(channel_layer.group_send)(
            f'room_{room_id}',
            {
                'type': 'participant_update',
                'participants': list(participants),
            }
        )

        return Response({'message': f'Successfully kicked {username}'}, status=status.HTTP_200_OK)
    except Room.DoesNotExist:
        return Response({'error': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_room_status(request, room_id):
    try:
        logger.debug(f"Updating status for room_id: {room_id}")
        room = Room.objects.get(room_id=room_id, is_active=True)
        if not RoomParticipant.objects.filter(room=room, user=request.user, role='host').exists():
            logger.warning(f"User {request.user.username} is not host for room {room_id}")
            return Response({'error': 'Only the host can update room status'}, status=status.HTTP_403_FORBIDDEN)

        new_status = request.data.get('status')
        if not new_status:
            logger.error(f"No status provided for room {room_id}")
            return Response({'error': 'Status is required'}, status=status.HTTP_400_BAD_REQUEST)

        logger.info(f"Changing room {room_id} status to {new_status}")
        room.status = new_status
        room.save()

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'room_{room_id}',
            {
                'type': 'room_update',
                'room': {
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
                    'join_code': room.join_code,
                    'is_ranked': room.is_ranked,
                }
            }
        )

        logger.info(f"Room {room_id} status updated successfully")
        return Response({'message': 'Room status updated'}, status=status.HTTP_200_OK)
    except Room.DoesNotExist:
        logger.error(f"Room not found or inactive: {room_id}")
        return Response({'error': 'Room not found or inactive'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error updating room {room_id} status: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class RoomQuestionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        try:
            room = Room.objects.get(room_id=room_id)
        except Room.DoesNotExist:
            return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)

        questions = Question.objects.filter(tags=room.topic, difficulty=room.difficulty)

        if not questions.exists():
            return Response({"error": "No questions available"}, status=status.HTTP_404_NOT_FOUND)

        question = random.choice(list(questions))
        
        examples = Example.objects.filter(question=question).values(
            'input_example', 'output_example', 'explanation'
        )


        response_data = {
            "id": question.id,
            "question_id": str(question.question_id),  
            "title": question.title,
            "slug": question.slug,
            "description": question.description,
            "difficulty": question.difficulty,
            "tags": question.tags,  
            "examples": list(examples),  
            "test_cases": [
                {
                    "id": tc.id,
                    "input_data": tc.input_data,
                    "expected_output": tc.expected_output,
                    "is_sample": tc.is_sample,
                    "order": tc.order
                } for tc in question.test_cases.all()
            ],
            "created_at": question.created_at,
            "updated_at": question.updated_at
        }

        return Response(response_data)
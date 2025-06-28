from django.shortcuts import render
from django.db.models import F, Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
import json
import logging
import traceback
from .models import Room, RoomParticipant
from .serializers import RoomCreateSerializer
from problems.models import Question, Example
from .utils.battle import select_random_question
from authentication.models import CustomUser
from django.db.models import F

logger = logging.getLogger(__name__)

class RoomListAPIView(APIView):
    def get(self, request):
        try:
            rooms = Room.objects.filter(is_active=True).values(
                'room_id', 'name', 'owner__username', 'topic', 'difficulty',
                'time_limit', 'capacity', 'participant_count', 'visibility', 'status', 'join_code', 'is_ranked'
            )
            return Response({'rooms': list(rooms)}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Failed to fetch rooms: {str(e)}")
            return Response({'error': f'Failed to fetch rooms: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CreateRoomAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = json.loads(request.body.decode('utf-8'))
            serializer = RoomCreateSerializer(data=data)
            if not serializer.is_valid():
                logger.error(f"Invalid input: {serializer.errors}")
                return Response({'error': 'Invalid input', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            validated_data = serializer.validated_data
            password = validated_data.get('password', '') if validated_data.get('visibility') != 'public' else ''

            try:
                room = Room.objects.create(
                    name=validated_data['name'],
                    topic=validated_data['topic'].upper(),
                    difficulty=validated_data['difficulty'].upper(),
                    time_limit=validated_data.get('time_limit', 0),
                    capacity=validated_data.get('capacity', 2),
                    visibility=validated_data.get('visibility', 'public'),
                    is_ranked=validated_data.get('is_ranked', False),
                    password=password,
                    owner=request.user,
                )
            except Exception as e:
                logger.error(f"Room creation failed: {str(e)}")
                traceback.print_exc()
                return Response({'error': 'Room creation failed', 'details': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            try:
                RoomParticipant.objects.create(
                    room=room,
                    user=request.user,
                    role='host',
                    status='joined',
                    ready=False,
                )
            except Exception as e:
                logger.error(f"Participant creation failed: {str(e)}")
                traceback.print_exc()
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

            return Response({
                'message': 'Room created successfully',
                'room_id': str(room.room_id),
                'room_name': room.name,
                'join_code': room.join_code,
                'owner': request.user.username,
                'is_ranked': room.is_ranked
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Internal server error: {str(e)}")
            return Response({'error': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RoomDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        try:
            room = Room.objects.select_related('owner').get(room_id=room_id)
            try:
                participant = RoomParticipant.objects.get(room=room, user=request.user)
                if participant.blocked:
                    return Response({'error': 'You are not authorised person'}, status=status.HTTP_404_NOT_FOUND)
            except RoomParticipant.DoesNotExist:
                return Response({'error': 'You are not authorised person'}, status=status.HTTP_404_NOT_FOUND)

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
            logger.error(f"Room not found: {room_id}")
            return Response({'error': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error fetching room details: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class JoinRoomAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        try:
            room = Room.objects.select_related('owner').get(room_id=room_id)
            participant = RoomParticipant.objects.filter(room=room, user=request.user).first()

            if participant:
                if participant.blocked:
                    return Response({'status': 'blocked', 'message': 'User is blocked from this room'}, status=status.HTTP_403_FORBIDDEN)
                participant.status = 'joined'
                participant.left_at = None
                participant.save()
                        
                room.participant_count = RoomParticipant.objects.filter(
                    room_id=room_id, status='joined'
                ).count()
                room.save()

                participants = RoomParticipant.objects.filter(room=room).values('user__username', 'role', 'status', 'ready')
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
                        'current_user': request.user.username,
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
            logger.error(f"Room not found: {room_id}")
            return Response({'error': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error joining room: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class KickParticipantAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
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
            logger.error(f"Room not found: {room_id}")
            return Response({'error': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error kicking participant: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class StartRoomAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        print("request post start room",request)
        try:
            logger.debug(f"Starting room: {room_id}")
            room = Room.objects.get(room_id=room_id, is_active=True)
            if not RoomParticipant.objects.filter(room=room, user=request.user, role='host').exists():
                logger.warning(f"User {request.user.username} is not host for room {room_id}")
                return Response({'error': 'Only the host can start the room'}, status=status.HTTP_403_FORBIDDEN)

            participants = RoomParticipant.objects.filter(room=room).values('user__username', 'role', 'status', 'ready')
            
            non_host_participants = [p for p in participants if p['role'] != 'host']
            capacity = room.capacity
            min_required = 2
            if capacity == 5:
                min_required = 3
            elif capacity == 10:
                min_required = 6

            if len(participants) < min_required:
                logger.error(f"Insufficient participants for room {room_id}: {len(participants)} < {min_required}")
                return Response({'error': f'At least {min_required} participants required to start'}, status=status.HTTP_400_BAD_REQUEST)

            if room.is_ranked and not all(p['ready'] for p in non_host_participants):
                logger.error(f"Not all non-host participants are ready for ranked room {room_id}")
                return Response({'error': 'All non-host participants must be ready for ranked mode'}, status=status.HTTP_400_BAD_REQUEST)

            selected_question = select_random_question(room)
            if not selected_question:
                logger.error(f"No valid questions found for room {room_id}")
                return Response({'error': 'No valid questions available for this room'}, status=status.HTTP_400_BAD_REQUEST)
            participant_users = CustomUser.objects.filter(
                room_participations__room=room
            ).distinct()
            participant_users.update(total_battles=F('total_battles') + 1)


            room.status = 'Playing'
            room.start_time=timezone.now()
            room.active_question = selected_question
            room.save()

            logger.info(f"Room {room_id} started successfully with question {selected_question.id}")
            return Response({
                'message': 'Room started successfully',
                'question_id': selected_question.id
            }, status=status.HTTP_200_OK)
        except Room.DoesNotExist:
            logger.error(f"Room not found or inactive: {room_id}")
            return Response({'error': 'Room not found or inactive'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error starting room {room_id}: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import Room, RoomParticipant
from django.utils import timezone


class WebSocketAuthMixin:
    @database_sync_to_async
    def get_user_from_token(self, token):
        try:
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            user = jwt_auth.get_user(validated_token)
            return user
        except AuthenticationFailed:
            return None
        except Exception as e:
            print(f"[ERROR] Token validation failed: {str(e)}")
            return None

    async def authenticate_user(self, query_string):
        token = None
        for param in query_string.decode().split('&'):
            if param.startswith('token='):
                token = param[len('token='):]
                break

        if not token:
            await self.close(code=4001, reason="No token provided")
            return None

        user = await self.get_user_from_token(token)
        if user is None or isinstance(user, AnonymousUser):
            await self.close(code=4002, reason="Invalid or expired token")
            return None

        return user


class RoomConsumer(AsyncWebsocketConsumer, WebSocketAuthMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_authenticated = False

    async def connect(self):
        user = await self.authenticate_user(self.scope['query_string'])
        if user is None:
            return

        self.scope['user'] = user
        print(f"[CONNECT] User {user} connected to room list")
        self.user_authenticated = True
        await self.channel_layer.group_add('rooms', self.channel_name)
        await self.accept()
        try:
            await self.send_room_list()
        except Exception as e:
            await self.close(code=4003, reason=f"Error sending room list: {str(e)}")

    async def disconnect(self, close_code):
        if hasattr(self, 'channel_name') and self.user_authenticated:
            print(f"[DISCONNECT] User {self.scope.get('user')} disconnected from room list")
            await self.channel_layer.group_discard('rooms', self.channel_name)

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            if message_type == 'request_room_list':
                await self.send_room_list()
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))

    async def room_update(self, event):
        try:
            await self.send(text_data=json.dumps({
                'type': 'room_update',
                'rooms': event['rooms']
            }))
        except Exception as e:
            await self.close(code=4004, reason=f"Error sending room update: {str(e)}")

    async def send_room_list(self):
        try:
            rooms = await database_sync_to_async(list)(
                Room.objects.filter(is_active=True).prefetch_related('participants').values(
                    'room_id', 'name', 'owner__username', 'topic', 'difficulty',
                    'time_limit', 'capacity', 'participant_count', 'visibility', 'status', 'is_ranked', 'join_code'
                )
            )
            processed_rooms = []
            for room in rooms:
                participants = await database_sync_to_async(list)(
                    RoomParticipant.objects.filter(room_id=room['room_id']).values(
                        'user__username', 'role', 'status', 'ready'
                    )
                )
                processed_rooms.append({
                    **room,
                    'room_id': str(room['room_id']),
                    'participants': participants
                })

            await self.send(text_data=json.dumps({
                'type': 'room_list',
                'rooms': processed_rooms
            }))
        except Exception as e:
            print(f"[ERROR] Error in send_room_list: {str(e)}")
            raise


class RoomLobbyConsumer(AsyncWebsocketConsumer, WebSocketAuthMixin):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'room_{self.room_id}'

        user = await self.authenticate_user(self.scope['query_string'])
        if user is None:
            return

        self.scope['user'] = user
        print(f"[CONNECT] User {user} joined room {self.room_id}")

        # Add or update participant record
        await self.ensure_participant(user, 'joined')

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        await self.send_participant_list()

    async def disconnect(self, close_code):
        print(f"[DISCONNECT] User {self.scope.get('user')} left room {self.room_id}")
        if hasattr(self, 'scope') and 'user' in self.scope and self.scope['user'].is_authenticated:
            participants = await self.update_participant_status('left')
            if participants:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'participant_update',
                        'participants': participants,
                    }
                )
                # Trigger room update to reflect participant_count
                await self.trigger_room_update()
        if hasattr(self, 'channel_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')

            if message_type == 'request_participants':
                await self.send_participant_list()

            elif message_type == 'chat_message':
                message = text_data_json.get('message')
                sender = self.scope['user'].username
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': message,
                        'sender': sender,
                    }
                )

            elif message_type == 'kick_participant':
                if await self.is_host(self.scope['user']):
                    target_username = text_data_json.get('username')
                    success = await self.kick_participant(target_username)
                    if success:
                        participants = await self.get_participants()
                        await self.channel_layer.group_send(
                            self.room_group_name,
                            {
                                'type': 'participant_update',
                                'participants': participants,
                            }
                        )

                        await self.trigger_room_update()
                    else:
                        await self.send(text_data=json.dumps({
                            'type': 'error',
                            'message': f'Failed to kick {target_username}'
                        }))
                else:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'Only the host can kick participants'
                    }))

            elif message_type == 'ready_toggle':
                ready = text_data_json.get('ready', False)
                await self.update_ready_status(ready)
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'ready_status',
                        'username': self.scope['user'].username,
                        'ready': ready,
                    }
                )

            elif message_type == 'start_countdown':
                if await self.is_host(self.scope['user']):
                    room = await self.get_room()
                    if room.is_ranked:
                        participants = await self.get_participants()
                        non_host_participants = [p for p in participants if p['role'] != 'host']
                        if not all(p['ready'] for p in non_host_participants):
                            await self.send(text_data=json.dumps({
                                'type': 'error',
                                'message': 'All participants must be ready for ranked mode'
                            }))
                            return
                    countdown = text_data_json.get('countdown', 5)
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'countdown',
                            'countdown': countdown,
                            'is_ranked': room.is_ranked,
                        }
                    )
                else:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'Only the host can start the countdown'
                    }))

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message'],
            'sender': event['sender'],
        }))

    async def participant_list(self, event):
        await self.send(text_data=json.dumps({
            'type': 'participant_list',
            'participants': event['participants'],
        }))

    async def participant_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'participant_update',
            'participants': event['participants'],
        }))

    async def ready_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'ready_status',
            'username': event['username'],
            'ready': event['ready'],
        }))

    async def countdown(self, event):
        await self.send(text_data=json.dumps({
            'type': 'countdown',
            'countdown': event['countdown'],
            'is_ranked': event['is_ranked'],
        }))

    @database_sync_to_async
    def get_participants(self):
        return list(RoomParticipant.objects.filter(room_id=self.room_id).values(
            'user__username', 'role', 'status', 'ready'
        ))

    @database_sync_to_async
    def get_room(self):
        try:
            return Room.objects.get(room_id=self.room_id)
        except Room.DoesNotExist:
            return None

    @database_sync_to_async
    def is_host(self, user):
        try:
            participant = RoomParticipant.objects.get(room_id=self.room_id, user=user)
            return participant.role == 'host'
        except RoomParticipant.DoesNotExist:
            return False

    @database_sync_to_async
    def kick_participant(self, target_username):
        try:
            participant = RoomParticipant.objects.get(
                room_id=self.room_id,
                user__username=target_username,
                status='joined'
            )
            participant.status = 'kicked'
            participant.left_at = timezone.now()
            participant.blocked = True
            participant.save()

            room = Room.objects.get(room_id=self.room_id)
            room.participant_count = RoomParticipant.objects.filter(
                room_id=self.room_id, status='joined'
            ).count()
            room.save()

            return True
        except RoomParticipant.DoesNotExist:
            print(f"[ERROR] Cannot kick {target_username}: Participant not found")
            return False

    @database_sync_to_async
    def ensure_participant(self, user, status):
        try:
            participant, created = RoomParticipant.objects.get_or_create(
                room_id=self.room_id,
                user=user,
                defaults={
                    'role': 'host' if Room.objects.get(room_id=self.room_id).owner == user else 'participant',
                    'status': status,
                    'joined_at': timezone.now(),
                    'ready': False,
                }
            )
            if not created:
                participant.status = status
                participant.left_at = None if status == 'joined' else timezone.now()
                participant.save()

            room = Room.objects.get(room_id=self.room_id)
            room.participant_count = RoomParticipant.objects.filter(
                room_id=self.room_id, status='joined'
            ).count()
            room.save()

            return participant
        except Room.DoesNotExist:
            print(f"[ERROR] Room {self.room_id} not found")
            return None

    async def update_participant_status(self, status):
        try:
            participant = await self.ensure_participant(self.scope['user'], status)
            if not participant:
                return None

            participants = await self.get_participants()
            print(f"[STATUS] {self.scope['user']} marked as {status} in room {self.room_id}")
            return participants
        except Exception as e:
            print(f"[ERROR] Failed to update participant status: {str(e)}")
            return await self.get_participants()

    @database_sync_to_async
    def update_ready_status(self, ready):
        try:
            participant = RoomParticipant.objects.get(room_id=self.room_id, user=self.scope['user'])
            participant.ready = ready
            participant.ready_at = timezone.now() if ready else None
            participant.save()
        except RoomParticipant.DoesNotExist:
            print(f"[ERROR] Participant {self.scope['user']} not found for ready status update")

    async def send_participant_list(self):
        try:
            participants = await self.get_participants()
            room = await self.get_room()
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'participant_list',
                    'participants': participants,
                    'is_ranked': room.is_ranked if room else False,
                }
            )
        except Exception as e:
            print(f"[ERROR] Error sending participant list: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Error sending participant list: {str(e)}'
            }))

    async def trigger_room_update(self):
        try:
            rooms = await database_sync_to_async(list)(
                Room.objects.filter(is_active=True).values(
                    'room_id', 'name', 'owner__username', 'topic', 'difficulty',
                    'time_limit', 'capacity', 'participant_count', 'visibility', 'status', 'is_ranked', 'join_code'
                )
            )
            processed_rooms = [{**room, 'room_id': str(room['room_id'])} for room in rooms]
            await self.channel_layer.group_send(
                'rooms',
                {
                    'type': 'room_update',
                    'rooms': processed_rooms,
                }
            )
        except Exception as e:
            print(f"[ERROR] Error triggering room update: {str(e)}")
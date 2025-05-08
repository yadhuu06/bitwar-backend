import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import Room, RoomParticipant

class WebSocketAuthMixin:
    """Mixin for common WebSocket authentication logic."""
    
    @database_sync_to_async
    def get_user_from_token(self, token):
        try:
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            user = jwt_auth.get_user(validated_token)
            return user
        except AuthenticationFailed:
            return None
        except Exception:
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

class RoomLobbyConsumer(AsyncWebsocketConsumer, WebSocketAuthMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_authenticated = False

    async def connect(self):
        user = await self.authenticate_user(self.scope['query_string'])
        if user is None:
            return

        self.scope['user'] = user
        self.user_authenticated = True
        await self.channel_layer.group_add('rooms', self.channel_name)
        await self.accept()
        try:
            await self.send_room_list()
        except Exception as e:
            await self.close(code=4003, reason=f"Error sending room list: {str(e)}")

    async def disconnect(self, close_code):
        if hasattr(self, 'channel_name') and self.user_authenticated:
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
                    'time_limit', 'capacity', 'participant_count', 'visibility', 'status', 'join_code'
                )
            )
            processed_rooms = []
            for room in rooms:
                participants = await database_sync_to_async(list)(
                    RoomParticipant.objects.filter(room_id=room['room_id']).values(
                        'user__username', 'role', 'status'
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
            print(f"Error in send_room_list: {str(e)}")
            raise

class RoomConsumer(AsyncWebsocketConsumer, WebSocketAuthMixin):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'room_{self.room_id}'

        user = await self.authenticate_user(self.scope['query_string'])
        if user is None:
            return

        self.scope['user'] = user
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        await self.send_participant_list()

    async def disconnect(self, close_code):
        if hasattr(self, 'scope') and 'user' in self.scope:
            await self.update_participant_status('left')
        if hasattr(self, 'channel_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            if message_type == 'request_participants':
                await self.send_participant_list()
            elif message_type == 'chat_message':
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': text_data_json.get('message'),
                        'sender': text_data_json.get('sender'),
                    }
                )
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
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

    @database_sync_to_async
    def get_participants(self):
        return list(RoomParticipant.objects.filter(room_id=self.room_id).values(
            'user__username', 'role', 'status'
        ))

    @database_sync_to_async
    def update_participant_status(self, status):
        try:
            participant = RoomParticipant.objects.get(room_id=self.room_id, user=self.scope['user'])
            participant.status = status
            participant.left_at = timezone.now()
            participant.save()
            participants = RoomParticipant.objects.filter(room_id=self.room_id).values('user__username', 'role', 'status')
            return list(participants)
        except RoomParticipant.DoesNotExist:
            return None

    async def send_participant_list(self):
        try:
            participants = await self.get_participants()
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'participant_list',
                    'participants': participants,
                }
            )
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Error sending participant list: {str(e)}'
            }))
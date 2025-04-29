
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Room
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed

class RoomConsumer(AsyncWebsocketConsumer):
   async def connect(self):
    query_string = self.scope['query_string'].decode()
    token = None
    for param in query_string.split('&'):
        if param.startswith('token='):
            token = param[len('token='):]
            break

    print(f"WebSocket connect attempt with token: {token}")
    if not token:
        print("No token provided, closing connection")
        await self.close(code=4001, reason="No token provided")
        return

    user = await self.get_user_from_token(token)
    if user is None or isinstance(user, AnonymousUser):
        print("Invalid or expired token, closing connection")
        await self.close(code=4002, reason="Invalid or expired token")
        return

    print(f"Authenticated user: {user}")
    self.scope['user'] = user
    await self.channel_layer.group_add('rooms', self.channel_name)
    await self.accept()
    await self.send_room_list()
    async def disconnect(self, close_code):
        if hasattr(self, 'channel_name'):
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
        await self.send(text_data=json.dumps({
            'type': 'room_update',
            'rooms': event['rooms']
        }))

    async def send_room_list(self):
        rooms = await database_sync_to_async(list)(
            Room.objects.filter(is_active=True).values(
                'room_id', 'name', 'owner__username', 'topic', 'difficulty',
                'time_limit', 'capacity', 'participant_count', 'visibility', 'status'
            )
        )
        rooms = [{**room, 'room_id': str(room['room_id'])} for room in rooms]
        await self.send(text_data=json.dumps({
            'type': 'room_list',
            'rooms': rooms
        }))

    @database_sync_to_async
    def get_user_from_token(self, token):
        try:
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            user = jwt_auth.get_user(validated_token)
            return user
        except AuthenticationFailed as e:
            print(f"Authentication failed: {str(e)}")
            return None

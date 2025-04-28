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

        user = await self.get_user_from_token(token)
        if user is None or isinstance(user, AnonymousUser):
            await self.close()
            return
        

        self.scope['user'] = user

        await self.channel_layer.group_add('rooms', self.channel_name)
        await self.accept()
        await self.send_room_list()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard('rooms', self.channel_name)

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type')
        if message_type == 'request_room_list':
            await self.send_room_list()

    async def room_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'room_update',
            'rooms': event['rooms']
        }))

    @database_sync_to_async
    def fetch_rooms(self):
        return Room.get_room_list()  

    async def send_room_list(self):
        rooms = await self.fetch_rooms()
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
        except AuthenticationFailed:
            return None

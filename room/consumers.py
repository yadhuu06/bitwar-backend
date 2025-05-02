import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import Room

class RoomConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        query_string = self.scope['query_string'].decode()
        print(f"Query string received: {query_string}")
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
        self.user_authenticated = True  
        print(f"Adding to group 'rooms' with channel: {self.channel_name}")
        await self.channel_layer.group_add('rooms', self.channel_name)
        print("Accepting WebSocket connection")
        await self.accept()
        print("Sending room list")
        try:
            await self.send_room_list()
            print("Room list sent successfully")
        except Exception as e:
            print(f"Error sending room list: {str(e)}")
            await self.close(code=4003, reason=f"Error sending room list: {str(e)}")

    async def disconnect(self, close_code):
        print(f"WebSocket disconnected with code: {close_code}, reason: {self.scope.get('close_reason', 'Unknown')}")
        if hasattr(self, 'channel_name') and self.user_authenticated:
            await self.channel_layer.group_discard('rooms', self.channel_name)

    async def receive(self, text_data):
  
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            if message_type == 'request_room_list':
                print("Received request_room_list, sending room list")
                await self.send_room_list()
            else:
                print(f"Unknown message type: {message_type}")
        except json.JSONDecodeError:
            print("Invalid JSON received")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))

    async def room_update(self, event):
        print(f"Sending room_update: {event}")
        try:
            await self.send(text_data=json.dumps({
                'type': 'room_update',
                'rooms': event['rooms']
            }))
        except Exception as e:
            print(f"Error sending room_update: {str(e)}")
            await self.close(code=4004, reason=f"Error sending room update: {str(e)}")

    async def send_room_list(self):
        try:
            print("Fetching room list")
            rooms = await database_sync_to_async(list)(
                Room.objects.filter(is_active=True).values(
                    'room_id', 'name', 'owner__username', 'topic', 'difficulty',
                    'time_limit', 'capacity', 'participant_count', 'visibility', 'status'
                )
            )
            print(f"Raw rooms data: {rooms}")
            rooms = [{**room, 'room_id': str(room['room_id'])} for room in rooms]
            print(f"Processed rooms data: {rooms}")
            await self.send(text_data=json.dumps({
                'type': 'room_list',
                'rooms': rooms
            }))
        except Exception as e:
            print(f"Error in send_room_list: {str(e)}")
            raise

    @database_sync_to_async
    def get_user_from_token(self, token):
        print(f"Validating token: {token}")
        try:
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            print(f"Validated token: {validated_token}")
            user = jwt_auth.get_user(validated_token)
            # print(f"Authenticated user: {user}")
            return user
        except AuthenticationFailed as e:
            print(f"Authentication failed: {str(e)}")
            return None
        except Exception as e:
            print(f"Unexpected error in token validation: {str(e)}")
            return None
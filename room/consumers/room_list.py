from room.consumers.base_consumer import BaseConsumer
from room.utils.auth import WebSocketAuthMixin
from room.services.room_service import get_room_list
from room.utils.error_handler import send_error

class RoomConsumer(BaseConsumer, WebSocketAuthMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_name = 'rooms'
        self.user_authenticated = False

    async def connect(self):
        user = await self.authenticate_user(self.scope['query_string'])
        if user is None:
            return

        self.scope['user'] = user
        print(f"[CONNECT] User {user} connected to room list")
        self.user_authenticated = True
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_room_list()

    async def disconnect(self, close_code):
        if self.user_authenticated:
            print(f"[DISCONNECT] User {self.scope.get('user')} disconnected from room list")
        await super().disconnect(close_code)

    async def handle_message(self, data):
        message_type = data.get('type')
        if message_type == 'request_room_list':
            await self.send_room_list()
        elif message_type == 'ping':
            await self.send_json({'type': 'pong'})
        else:
            await send_error(self, f"Unknown message type: {message_type}")

    async def room_update(self, event):
        await self.send_json({
            'type': 'room_update',
            'rooms': event['rooms']
        })

    async def send_room_list(self):
        try:
            rooms = await get_room_list()
            await self.send_json({
                'type': 'room_list',
                'rooms': rooms
            })
        except Exception as e:
            await send_error(self, f"Error sending room list: {str(e)}")
            await self.close(code=4003)
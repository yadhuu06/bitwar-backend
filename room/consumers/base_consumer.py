import json
from channels.generic.websocket import AsyncWebsocketConsumer
from room.utils.error_handler import send_error

class BaseConsumer(AsyncWebsocketConsumer):
    async def send_json(self, data):
        """Send JSON data to the client."""
        try:
            await self.send(text_data=json.dumps(data))
        except Exception as e:
            await self.close(code=4000, reason=f"Error sending data: {str(e)}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            text_data_json = json.loads(text_data)
            await self.handle_message(text_data_json)
        except json.JSONDecodeError:
            await send_error(self, "Invalid JSON format")

    async def handle_message(self, data):
        """To be overridden by subclasses."""
        await send_error(self, "Message type not supported")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'group_name') and hasattr(self, 'channel_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
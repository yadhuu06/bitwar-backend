from room.consumers.base_consumer import BaseConsumer
from room.utils.error_handler import send_error
import json

class BattleConsumer(BaseConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.group_name = f"battle_{self.room_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await super().disconnect(close_code)

    async def handle_message(self, data):
        message_type = data.get('type')
        if message_type == 'code_verified':
            await self.handle_code_verified(data)
        elif message_type == 'battle_completed':
            await self.battle_completed(data)
        else:
            await send_error(self, 'Unknown message type')

    async def handle_code_verified(self, data):
        await self.send_json({
            'type': 'code_verified',
            'username': data['username'],
            'position': data['position'],
            'message': f"{data['username']} submitted correct code (Position: {data['position']})",
            'completion_time': data['completion_time']
        })

    async def battle_completed(self, event):
        await self.send_json({
            'type': 'battle_completed',
            'username': event['user'],
            'question_id': event['question_id'],
            'winners': event['winners'],
            'message': f"Battle completed! Winners: {[w['username'] for w in event['winners']]}"
        })
# battle/consumers.py

from room.consumers.base_consumer import BaseConsumer
from room.utils.error_handler import send_error

class BattleConsumer(BaseConsumer):
    async def handle_message(self, data):
        message_type = data.get('type')

        if message_type == 'code_verified':
            await self.handle_code_verified(data)
        
        else:
            await send_error(self, 'Unknown message type')

    async def handle_code_verified(self, data):
      
        pass

    async def battle_completed(self, event):
        await self.send_json({
            'type': 'battle_completed',
            'username': event['user'],
            'question_id': event['question_id']
        })

from room.consumers.base_consumer import BaseConsumer
from room.utils.error_handler import send_error
from room.models import Room
from battle.models import BattleResult
from asgiref.sync import sync_to_async
from django.utils import timezone
import json
import asyncio

class BattleConsumer(BaseConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.group_name = f"battle_{self.room_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        
        room = await sync_to_async(Room.objects.filter(room_id=self.room_id).first)()
        if room and room.start_time and room.time_limit > 0:
            asyncio.create_task(self.send_time_updates())

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await super().disconnect(close_code)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            await self.handle_message(data)
        except json.JSONDecodeError:
            await send_error(self, 'Invalid JSON format')

    async def handle_message(self, data):
        message_type = data.get('type')
        if message_type=='ping':
                await self.send(text_data=json.dumps({"type": "pong"}))
        elif message_type == 'code_verified':
            await self.handle_code_verified(data)
        elif message_type == 'battle_completed':
            await self.battle_completed(data)
        elif message_type == 'battle_started':
            await self.battle_started(data)
        elif message_type == 'start_countdown':
            await self.start_countdown(data)
        elif message_type == 'time_update':
            await self.time_update(data)
        else:
            await send_error(self, f'Unknown message type: {message_type}')

    async def handle_code_verified(self, data):
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'code_verified',
                'username': data['username'],
                'position': data['position'],
                'message': f"{data['username']} finished {self.get_ordinal(data['position'])}!",
                'completion_time': data['completion_time']
            }
        )

    async def code_verified(self, event):
        await self.send_json({
            'type': 'code_verified',
            'username': event['username'],
            'position': event['position'],
            'message': event['message'],
            'completion_time': event['completion_time']
        })

    async def battle_completed(self, event):
        room = await sync_to_async(Room.objects.filter(room_id=self.room_id).first)()
        max_winners = {2: 1, 5: 2, 10: 3}.get(room.capacity, 1)
        winners = event.get('winners', [])[:max_winners]
        await self.send_json({
            'type': 'battle_completed',
            'username': event.get('user', ''),
            'question_id': event.get('question_id', ''),
            'winners': winners,
            'room_capacity': room.capacity,
            'message': event.get('message', 'Battle Ended!')
        })

    async def battle_started(self, event):
        await self.send_json({
            'type': 'battle_started',
            'message': event.get('message', 'Battle started!'),
            'start_time': event.get('start_time', ''),
            'time_limit': event.get('time_limit', 0)
        })

    async def start_countdown(self, event):
        await self.send_json({
            'type': 'start_countdown',
            'message': event.get('message', f"Battle starting in {event.get('countdown', 0)} seconds!"),
            'countdown': event.get('countdown', 0),
            'question_id': event.get('question_id', '')
        })

    async def time_update(self, event):
        await self.send_json({
            'type': 'time_update',
            'remaining_seconds': event['remaining_seconds']
        })

    async def send_time_updates(self):
        room = await sync_to_async(Room.objects.filter(room_id=self.room_id).first)()
        while room and room.status == 'Playing' and room.time_limit > 0:
            elapsed_seconds = (timezone.now() - room.start_time).total_seconds()
            remaining_seconds = max(0, room.time_limit * 60 - elapsed_seconds)
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'time_update',
                    'remaining_seconds': round(remaining_seconds, 2)
                }
            )
            if remaining_seconds <= 0:
                room.status = 'completed'
                await sync_to_async(room.save)()
                battle_result = await sync_to_async(BattleResult.objects.filter(room=room).first)()
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        'type': 'battle_completed',
                        'message': 'Battle ended due to time limit!',
                        'winners': battle_result.results[:{2: 1, 5: 2, 10: 3}.get(room.capacity, 1)] if battle_result else [],
                        'room_capacity': room.capacity
                    }
                )
                break
            await asyncio.sleep(10)
            room = await sync_to_async(Room.objects.filter(room_id=self.room_id).first)()

    def get_ordinal(self, n):
        s = ["th", "st", "nd", "rd"]
        v = n % 100
        return f"{n}{s[(v - 20) % 10] if (v - 20) % 10 < 4 else s[0]}"
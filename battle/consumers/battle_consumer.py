import json
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from room.utils.auth import WebSocketAuthMixin
from problems.models import Question
from room.models import Room
from room.utils.error_handler import send_error

class BattleConsumer(AsyncWebsocketConsumer, WebSocketAuthMixin):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'battle_{self.room_id}'
        self.user = await self.authenticate_user(self.scope['query_string'])
        
        if not self.user:
            await self.close(code=4001)
            return
        
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        await self.send_json({
            'type': 'connected',
            'message': f'Connected to battle room: {self.room_id}'
        })

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'submit_code':
                await self.handle_submission(data)
            else:
                await send_error(self, f"Unknown message type: {message_type}")

        except Exception as e:
            await send_error(self, f"Error: {str(e)}")

    async def handle_submission(self, data):
        """
        Receive code submissions and broadcast result
        """
        question_id = data.get('question_id')
        submitted_code = data.get('code')
        language = data.get('language')

        if not question_id or not submitted_code or not language:
            await send_error(self, 'Incomplete submission data')
            return

        # Simulate result (later you will call your judge/verification system here)
        result = {
            'passed': True,
            'test_cases': [
                {'test_case_id': 1, 'result': 'Passed'},
                {'test_case_id': 2, 'result': 'Passed'}
            ]
        }

        # Broadcast to all clients
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'submission_result',
                'username': self.user.username,
                'question_id': question_id,
                'result': result
            }
        )

    async def submission_result(self, event):
        await self.send_json({
            'type': 'submission_result',
            'username': event['username'],
            'question_id': event['question_id'],
            'result': event['result']
        })

    @database_sync_to_async
    def get_question(self, question_id):
        try:
            return Question.objects.get(id=question_id)
        except Question.DoesNotExist:
            return None

    @database_sync_to_async
    def get_room(self):
        try:
            return Room.objects.get(room_id=self.room_id)
        except Room.DoesNotExist:
            return None

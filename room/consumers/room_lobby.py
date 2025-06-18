from channels.db import database_sync_to_async
from django.utils import timezone
from room.models import Room, RoomParticipant
from room.consumers.base_consumer import BaseConsumer
from room.services.room_service import get_room, close_room, get_room_list
from room.services.participant_service import (
    ensure_participant, get_participants, check_participant, update_participant_status,
    update_ready_status, kick_participant
)
from room.services.chat_service import save_chat_message, get_chat_history, clear_chat_messages
from room.utils.auth import WebSocketAuthMixin
from room.utils.error_handler import send_error
from problems.models import Question, Example,TestCase
from django.db.models import Q
import random

class RoomLobbyConsumer(BaseConsumer, WebSocketAuthMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.room_id = None
        self.room_group_name = None
        self.user = None

    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'room_{self.room_id}'
        user = await self.authenticate_user(self.scope['query_string'])
        if user is None:
            return

        room = await get_room(self.room_id)
        if not room:
            await send_error(self, "Room not found", code=4005)
            return

        self.user = user
        self.scope['user'] = user
        is_host = await self.is_host()
        if room.visibility == 'private' and not is_host:
            is_allowed = await check_participant(user, self.room_id)
            if not is_allowed:
                await send_error(self, "Not authorized to join private room", code=4005)
                return

        print(f"[CONNECT] User {user} joined room {self.room_id}")
        await ensure_participant(self.room_id, user, 'joined')
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        await self.send_system_message(f"{user.username} joined the lobby")
        await self.send_participant_list()
        await self.send_chat_history()

    async def disconnect(self, close_code):
        if self.user and self.user.is_authenticated:
            print(f"[DISCONNECT] User {self.user} left room {self.room_id}")
            participants = await update_participant_status(self.room_id, self.user, 'left')
            if participants:
                await self.broadcast_participant_update(participants)
                await self.send_system_message(f"{self.user.username} left the lobby")
                await self.broadcast({
                    'type': 'participant_left',
                    'username': self.user.username,
                })
                await self.trigger_room_update()
        await super().disconnect(close_code)

    async def handle_message(self, data):
        message_type = data.get('type')
        handlers = {
            'request_participants': self.handle_request_participants,
            'chat_message': self.handle_chat_message,
            'kick_participant': self.handle_kick_participant,
            'ready_toggle': self.handle_ready_toggle,
            'start_countdown': self.handle_start_countdown,
            'start_battle': self.handle_start_battle,
            'close_room': self.handle_close_room,
            'leave_room': self.handle_leave_room,
            'ping': self.handle_ping,
            'request_chat_history': self.handle_request_chat_history,
        }
        handler = handlers.get(message_type)
        if handler:
            await handler(data)
        else:
            await send_error(self, f"Unknown message type: {message_type}")

    async def handle_request_participants(self, data):
        await self.send_participant_list()

    async def handle_chat_message(self, data):
        message = data.get('message')
        sender = data.get('sender', self.user.username)
        if not message.strip():
            await send_error(self, "Message cannot be empty")
            return
        await save_chat_message(self.room_id, message, sender, is_system=False)
        await self.broadcast({
            'type': 'chat_message',
            'message': message,
            'sender': sender,
            'timestamp': timezone.now().strftime('%I:%M %p'),
            'is_system': False,
        })

    async def handle_kick_participant(self, data):
        if not await self.is_host():
            await send_error(self, "Only the host can kick participants")
            return
        target_username = data.get('username')
        success = await kick_participant(self.room_id, target_username)
        if success:
            participants = await get_participants(self.room_id)
            await self.broadcast_participant_update(participants)
            await self.broadcast({
                'type': 'kicked',
                'username': target_username,
            })
            await self.send_system_message(f"{target_username} has been kicked")
            await self.trigger_room_update()
        else:
            await send_error(self, f"Failed to kick {target_username}")

    async def handle_ready_toggle(self, data):
        ready = data.get('ready', False)
        await update_ready_status(self.room_id, self.user, ready)
        await self.broadcast({
            'type': 'ready_status',
            'username': self.user.username,
            'ready': ready,
        })

    async def handle_start_countdown(self, data):
        if not await self.is_host():
            await send_error(self, "Only the host can start the countdown")
            return
        room = await get_room(self.room_id)
        if room.is_ranked:
            participants = await get_participants(self.room_id)
            non_host_participants = [p for p in participants if p['role'] != 'host']
            if not all(p['ready'] for p in non_host_participants):
                await send_error(self, "All participants must be ready for ranked mode")
                return
        countdown = data.get('countdown', 5)
        await self.broadcast({
            'type': 'countdown',
            'countdown': countdown,
            'is_ranked': room.is_ranked,
        })

    async def handle_start_battle(self, data):
        if not await self.is_host():
            await send_error(self, "Only the host can start the battle")
            return
        room = await get_room(self.room_id)
        if not room:
            await send_error(self, "Room not found", code=4005)
            return
        if room.status != 'Playing':
            await send_error(self, "Room is not in Playing status")
            return

        questions = await self.database_sync_to_async(
            lambda: Question.objects.filter(
                tags=room.topic,
                difficulty=room.difficulty
            ).filter(
                Q(is_contributed=False) |
                Q(is_contributed=True, contribution_status="Accepted")
            ).exclude(
                is_validated=False
            )
        )()
        if not questions:
            await send_error(self, "No questions available", code=4004)
            return

        question = random.choice(list(questions))
        room.active_question = question
        await self.database_sync_to_async(room.save)()

        examples = await self.database_sync_to_async(
            lambda: list(Example.objects.filter(question=question).values(
                'input_example', 'output_example', 'explanation'
            ))
        )()
        testCases=await self.database_sync_to_async(lambda:list(TestCase.objects.filter(question=question)))

        question_data = {
            'id': question.id,
            'title': question.title,
            'description': question.description,
            'tags': question.tags,
            'difficulty': question.difficulty,
            'examples': examples,
            'testcases':testCases
        }


        await self.broadcast({
            'type': 'battle_started',
            'question': question_data,
            'room_id': str(room.room_id),
        })

    async def handle_close_room(self, data):
        if not await self.is_host():
            await send_error(self, "Only the host can close the room")
            return
        await close_room(self.room_id)
        await self.send_system_message("Room closed. Chat cleared.")
        await self.broadcast({
            'type': 'room_closed',
        })
        await clear_chat_messages(self.room_id)
        await self.trigger_room_update()

    async def handle_leave_room(self, data):
        participants = await update_participant_status(self.room_id, self.user, 'left')
        if participants:
            await self.broadcast_participant_update(participants)
            await self.send_system_message(f"{self.user.username} left the lobby")
            await self.broadcast({
                'type': 'participant_left',
                'username': self.user.username,
            })
            await self.trigger_room_update()

    async def handle_ping(self, data):
        await self.send_json({'type': 'pong'})

    async def handle_request_chat_history(self, data):
        await self.send_chat_history()

    async def send_system_message(self, message):
        await save_chat_message(self.room_id, message, sender="System", is_system=True)
        await self.broadcast({
            'type': 'chat_message',
            'message': message,
            'sender': 'System',
            'timestamp': timezone.now().strftime('%I:%M %p'),
            'is_system': True,
        })

    async def send_participant_list(self):
        participants = await get_participants(self.room_id)
        room = await get_room(self.room_id)
        if not room:
            await send_error(self, "Room not found")
            return
        await self.broadcast({
            'type': 'participant_list',
            'participants': participants,
            'is_ranked': room.is_ranked,
        })

    async def broadcast_participant_update(self, participants):
        await self.broadcast({
            'type': 'participant_update',
            'participants': participants,
        })

    async def send_chat_history(self):
        messages = await get_chat_history(self.room_id)
        await self.send_json({
            'type': 'chat_history',
            'messages': messages
        })

    async def is_host(self):
        participants = await get_participants(self.room_id)
        return any(
            p['user__username'] == self.user.username and p['role'] == 'host'
            for p in participants
        )

    async def broadcast(self, message):
        await self.channel_layer.group_send(self.room_group_name, message)

    async def trigger_room_update(self):
        try:
            rooms = await get_room_list()
            await self.channel_layer.group_send(
                'rooms',
                {
                    'type': 'room_update',
                    'rooms': rooms,
                }
            )
        except Exception as e:
            print(f"[ERROR] Error triggering room update: {str(e)}")

    async def database_sync_to_async(self, func):
        from asgiref.sync import sync_to_async
        return await sync_to_async(func)()

    async def chat_message(self, event):
        await self.send_json(event)

    async def participant_list(self, event):
        await self.send_json(event)

    async def participant_update(self, event):
        await self.send_json(event)

    async def ready_status(self, event):
        await self.send_json(event)

    async def countdown(self, event):
        await self.send_json(event)

    async def battle_started(self, event):
        await self.send_json(event)

    async def kicked(self, event):
        await self.send_json(event)

    async def room_closed(self, event):
        await self.send_json(event)

    async def participant_left(self, event):
        await self.send_json(event)
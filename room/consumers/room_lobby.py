import asyncio
import logging
from django.utils import timezone
from room.consumers.base_consumer import BaseConsumer
from room.services.room_service import get_room, close_room, get_room_list
from room.services.participant_service import (
    ensure_participant, get_participants, check_participant, update_participant_status,
    update_ready_status, kick_participant
)
from room.services.chat_service import save_chat_message, get_chat_history, clear_chat_messages
from room.utils.auth import WebSocketAuthMixin
from room.utils.error_handler import send_error
from room.utils.error_codes import ERRORS
import json

logger = logging.getLogger(__name__)

class RoomLobbyConsumer(BaseConsumer, WebSocketAuthMixin):


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.room_id = None
        self.room_group_name = None
        self.user = None

    async def connect(self):
        """Handle WebSocket connection and initialize room and user data."""
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'room_{self.room_id}'
        user = await self.authenticate_user(self.scope['query_string'])
        
        if not user:
            await self._send_error('AUTH_FAILED')
            return

        room = await self._get_valid_room()
        if not room:
            return

        self.user = user
        self.scope['user'] = user
        is_host = await self.is_host()
        
        if room.visibility == 'private' and not is_host:
            is_allowed = await check_participant(user, self.room_id)
            if not is_allowed:
                await self._send_error('PRIVATE_ROOM_NOT_AUTHORIZED')
                return

        logger.info(f"[CONNECT] User {user.username} joined room {self.room_id}")
        await ensure_participant(self.room_id, user, 'joined')
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        await self._send_and_broadcast_system_message(f"{user.username} joined the lobby")
        await self._broadcast_participant_list()
        await self.send_chat_history()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection and update participant status."""
        if self.user and self.user.is_authenticated:
            logger.info(f"[DISCONNECT] User {self.user.username} left room {self.room_id}")
            await self._handle_participant_leave()
        await super().disconnect(close_code)

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            logger.debug(f"[RECEIVE] Room {self.room_id} message: {data}")
            await self.handle_message(data)
        except json.JSONDecodeError:
            await self._send_error('INVALID_MESSAGE_FORMAT')

    async def handle_message(self, data):
        """Route incoming messages to appropriate handlers."""
        message_type = data.get('type')
        handlers = {
            'request_participants': self.handle_request_participants,
            'chat_message': self.handle_chat_message,
            'kick_participant': self.handle_kick_participant,
            'ready_toggle': self.handle_ready_toggle,
            'start_countdown': self.handle_start_countdown,
            'close_room': self.handle_close_room,
            'leave_room': self.handle_leave_room,
            'ping': self.handle_ping,
            'request_chat_history': self.handle_request_chat_history,
        }
        handler = handler = handlers.get(message_type)
        if handler:
            await handler(data)
        else:
            await self._send_error('UNKNOWN_MESSAGE_TYPE', message_type)

    async def handle_request_participants(self, data):
        """Send the current participant list to the client."""
        await self._broadcast_participant_list()

    async def handle_chat_message(self, data):
        """Handle and broadcast a chat message."""
        message = data.get('message')
        sender = data.get('sender', self.user.username)
        if not message or not message.strip():
            await self._send_error('EMPTY_MESSAGE')
            return
        await save_chat_message(self.room_id, message, sender, is_system=False)
        await self._broadcast({
            'type': 'chat_message',
            'message': message,
            'sender': sender,
            'timestamp': timezone.now().strftime('%I:%M %p'),
            'is_system': False,
        })

    async def handle_kick_participant(self, data):
        """Handle kicking a participant (host only)."""
        if not await self.is_host():
            await self._send_error('HOST_ONLY_KICK')
            return
        target_username = data.get('username')
        if not target_username:
            await self._send_error('USERNAME_REQUIRED')
            return
        success = await kick_participant(self.room_id, target_username)
        if success:
            await self._send_and_broadcast_system_message(f"{target_username} has been kicked")
            await self._broadcast_participant_list()
            await self._broadcast({
                'type': 'kicked',
                'username': target_username,
            })
            await self._trigger_room_update()
        else:
            await self._send_error('KICK_FAILED', target_username)

    async def handle_ready_toggle(self, data):
        """Toggle the ready status of a participant."""
        ready = data.get('ready', False)
        await update_ready_status(self.room_id, self.user, ready)
        await self._broadcast({
            'type': 'ready_status',
            'username': self.user.username,
            'ready': ready,
        })

    async def handle_start_countdown(self, data):
        """Start the countdown for a battle (host only)."""
        if not await self.is_host():
            await self._send_error('HOST_ONLY_COUNTDOWN')
            return

        room = await self._get_valid_room()
        if not room:
            return

        if not room.active_question:
            await self._send_error('NO_QUESTION_SELECTED')
            return

        if room.is_ranked:
            participants = await get_participants(self.room_id)
            non_host_participants = [p for p in participants if p['role'] != 'host']
            if not all(p['ready'] for p in non_host_participants):
                await self._send_error('RANKED_NOT_READY')
                return

        logger.info(f"[START_COUNTDOWN] Room {self.room_id} starting with question {room.active_question.id}")

        await self._broadcast({
            'type': 'battle_ready',
            'room_id': str(room.room_id),
            'question': {
                'id': room.active_question.id,
                'title': room.active_question.title,
                'difficulty': room.active_question.difficulty,
            }
        })

        countdown = data.get('countdown', 5)
        for i in range(countdown, -1, -1):
            await self._broadcast({
                'type': 'countdown',
                'countdown': i,
                'is_ranked': room.is_ranked,
            })
            await asyncio.sleep(1)

        logger.info(f"[BATTLE_STARTED] Room {self.room_id} navigating to battle with question {room.active_question.id}")
        await self._broadcast({
            'type': 'battle_started',
            'room_id': str(room.room_id),
            'question': {
                'id': room.active_question.id,
            }
        })

    async def handle_close_room(self, data):
        """Close the room and clear chat (host only)."""
        if not await self.is_host():
            await self._send_error('HOST_ONLY_CLOSE')
            return
        success = await close_room(self.room_id)
        if success:
            await self._send_and_broadcast_system_message("Room closed. Chat cleared.")
            await self._broadcast({
                'type': 'room_closed',
            })
            await clear_chat_messages(self.room_id)
            await self._trigger_room_update()
        else:
            await self._send_error('CLOSE_ROOM_FAILED')

    async def handle_leave_room(self, data):
        """Handle a participant leaving the room."""
        await self._handle_participant_leave()

    async def handle_ping(self, data):
        """Respond to a ping message with a pong."""
        await self.send_json({'type': 'pong'})

    async def handle_request_chat_history(self, data):
        """Send the chat history to the client."""
        await self.send_chat_history()

    async def _send_error(self, error_key, *args):
        """Send an error message using the centralized error codes."""
        error = ERRORS.get(error_key, {'message': 'Unknown error', 'code': 4000})
        message = error['message'].format(*args) if args else error['message']
        await send_error(self, message, code=error['code'])

    async def _get_valid_room(self):
        """Retrieve and validate a room, sending an error if not found."""
        room = await get_room(self.room_id)
        if not room:
            await self._send_error('ROOM_NOT_FOUND')
            return None
        logger.debug(f"[GET_ROOM] Room {self.room_id}: is_ranked={room.is_ranked}, active_question={room.active_question}")
        return room

    async def _send_and_broadcast_system_message(self, message):
        """Save and broadcast a system message."""
        await save_chat_message(self.room_id, message, sender="System", is_system=True)
        await self._broadcast({
            'type': 'chat_message',
            'message': message,
            'sender': 'System',
            'timestamp': timezone.now().strftime('%I:%M %p'),
            'is_system': True,
        })

    async def _broadcast_participant_list(self):
        """Broadcast the current participant list and room details."""
        room = await self._get_valid_room()
        if not room:
            return
        participants = await get_participants(self.room_id)
        await self._broadcast({
            'type': 'participant_list',
            'participants': participants,
            'is_ranked': room.is_ranked,
        })

    async def _handle_participant_leave(self):
        """Handle participant leaving and broadcast updates."""
        participants = await update_participant_status(self.room_id, self.user, 'left')
        if participants:
            await self._send_and_broadcast_system_message(f"{self.user.username} left the lobby")
            await self._broadcast({
                'type': 'participant_update',
                'participants': participants,
            })
            await self._broadcast({
                'type': 'participant_left',
                'username': self.user.username,
            })
            await self._trigger_room_update()

    async def _broadcast(self, message):
        """Broadcast a message to the room group."""
        await self.channel_layer.group_send(self.room_group_name, message)

    async def _trigger_room_update(self):
        """Trigger an update to the room list for all clients."""
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
            logger.error(f"[ERROR] Error triggering room update: {str(e)}")

    async def is_host(self):
        """Check if the current user is the host of the room."""
        participants = await get_participants(self.room_id)
        return any(
            p['user__username'] == self.user.username and p['role'] == 'host'
            for p in participants
        )

    async def send_chat_history(self):
        """Send the chat history to the connected client."""
        messages = await get_chat_history(self.room_id)
        await self.send_json({
            'type': 'chat_history',
            'messages': messages,
        })

    # Message handlers for group messages
    async def chat_message(self, event):
        await self.send_json(event)

    async def participant_list(self, event):
        await self.send_json(event)

    async def participant_update(self, event):
        await self.send_json(event)

    async def ready_status(self, event):
        await self.send_json(event)

    async def battle_ready(self, event):
        logger.debug(f"[BATTLE_READY] Forwarding to room {self.room_id}: {event}")
        await self.send_json(event)

    async def countdown(self, event):
        logger.debug(f"[COUNTDOWN] Forwarding to room {self.room_id}: {event}")
        await self.send_json(event)

    async def battle_started(self, event):
        logger.debug(f"[BATTLE_STARTED] Forwarding to room {self.room_id}: {event}")
        await self.send_json(event)

    async def kicked(self, event):
        await self.send_json(event)

    async def room_closed(self, event):
        await self.send_json(event)

    async def participant_left(self, event):
        await self.send_json(event)
# room/utils/error_codes.py
ERRORS = {
    'AUTH_FAILED': {'message': 'Authentication failed', 'code': 4001},
    'INVALID_MESSAGE_FORMAT': {'message': 'Invalid message format', 'code': 4003},
    'UNKNOWN_MESSAGE_TYPE': {'message': 'Unknown message type: {}', 'code': 4004},
    'ROOM_NOT_FOUND': {'message': 'Room not found', 'code': 4005},
    'EMPTY_MESSAGE': {'message': 'Message cannot be empty', 'code': 4006},
    'HOST_ONLY_KICK': {'message': 'Only the host can kick participants', 'code': 4007},
    'USERNAME_REQUIRED': {'message': 'Username is required', 'code': 4008},
    'KICK_FAILED': {'message': 'Failed to kick {}', 'code': 4009},
    'HOST_ONLY_COUNTDOWN': {'message': 'Only the host can start the countdown', 'code': 4010},
    'RANKED_NOT_READY': {'message': 'All participants must be ready for ranked mode', 'code': 4011},
    'HOST_ONLY_CLOSE': {'message': 'Only the host can close the room', 'code': 4012},
    'CLOSE_ROOM_FAILED': {'message': 'Failed to close room', 'code': 4013},
    'PRIVATE_ROOM_NOT_AUTHORIZED': {'message': 'Not authorized to join private room', 'code': 4005},
}
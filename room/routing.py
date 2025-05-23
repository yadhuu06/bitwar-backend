from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/rooms/$', consumers.RoomConsumer.as_asgi()),
    re_path(
        r'ws/rooms/(?P<room_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/$',
        consumers.RoomLobbyConsumer.as_asgi()
    ),
]
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/rooms/$', consumers.RoomConsumer.as_asgi()),
    re_path(r'ws/room/(?P<room_id>[0-9a-f-]+)/$', consumers.RoomInstanceConsumer.as_asgi()), 
]
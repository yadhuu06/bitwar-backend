from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/rooms/$', consumers.RoomLobbyConsumer.as_asgi()),
    re_path(r'ws/rooms/(?P<room_id>[^/]+)/$', consumers.RoomConsumer.as_asgi())

]
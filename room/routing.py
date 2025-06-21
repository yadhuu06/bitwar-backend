from django.urls import re_path
from room.consumers.room_list import RoomConsumer
from room.consumers.room_lobby import RoomLobbyConsumer
from battle.consumers.battle_consumer import BattleConsumer

websocket_urlpatterns = [
    re_path(r'^ws/rooms/$', RoomConsumer.as_asgi()),
    re_path(r'^ws/room/(?P<room_id>[^/]+)/?$', RoomLobbyConsumer.as_asgi()),
    re_path(r'^ws/battle/(?P<room_id>[^/]+)/$', BattleConsumer.as_asgi()),
]



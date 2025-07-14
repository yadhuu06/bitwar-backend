from django.urls import re_path
from battle.consumers.battle_consumer import BattleConsumer

websocket_urlpatterns = [
    re_path(r'^ws/battle/(?P<room_id>[^/]+)/$', BattleConsumer.as_asgi()),
]

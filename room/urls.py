from django.urls import path
from .views import (
    RoomListAPIView, CreateRoomAPIView, RoomDetailAPIView,
    JoinRoomAPIView, KickParticipantAPIView, StartRoomAPIView
)

urlpatterns = [
    path('', RoomListAPIView.as_view(), name='room'),
    path('create/', CreateRoomAPIView.as_view(), name='create_room'),
    path('<uuid:room_id>/', RoomDetailAPIView.as_view(), name='get_room_details'),
    path('<uuid:room_id>/join/', JoinRoomAPIView.as_view(), name='join_room'),
    path('<uuid:room_id>/kick/', KickParticipantAPIView.as_view(), name='kick_participant'),
    path('<uuid:room_id>/start/', StartRoomAPIView.as_view(), name='start_room'),
]
from django.urls import path
from .views import room_view,RoomCreateAPIView
urlpatterns = [
    path('', room_view, name='room'),
    path('create/', RoomCreateAPIView.as_view(), name='room-create'),
    
]
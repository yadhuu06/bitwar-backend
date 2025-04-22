from django.urls import path
from .views import room_view,create_room
from . import views
urlpatterns = [
    path('', room_view, name='room'),
    path('create/', create_room, name='create_room'),
    
]
from django.urls import path
from .views import room_view,create_room,join_room_view
from . import views
urlpatterns = [
    path('', room_view, name='room'),
    path('create/', create_room, name='create_room'),
    path('<uuid:room_id>/join/', views.join_room_view, name='join_room'),
       
]

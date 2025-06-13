from django.urls import path
from . import views
from .views import RoomQuestionAPIView

urlpatterns = [
    path('', views.room_view, name='room'),
    path('create/', views.create_room, name='create_room'),
    path('<uuid:room_id>/', views.get_room_details_view, name='get_room_details'),
    path('<uuid:room_id>/join/', views.join_room_view, name='join_room'),
    path('<uuid:room_id>/kick/', views.kick_participant_view, name='kick_participant'),
    path('rooms/<int:room_id>/question/', RoomQuestionAPIView, name='room-question')

]
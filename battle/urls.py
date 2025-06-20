from django.urls import path


urlpatterns = [
    
    path('<uuid:room_id>/', BattleQuestion.as_view(), name='get_room_details'),
    
]
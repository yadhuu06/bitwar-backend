from django.urls import path
from .views import room_view
urlpatterns = [
    path('', room_view, name='register'),
    
]
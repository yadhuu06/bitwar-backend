from django.urls import path
from .views import users_list,toggle_block_user

urlpatterns = [
 path('users_list/', users_list, name='users_list'),
 path('users/toggle-block/', toggle_block_user, name='toggle_block_user'),
]

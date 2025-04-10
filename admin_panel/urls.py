from django.urls import path
from .views import users_list,toggle_block_user,admin_login

urlpatterns = [
 path('users_list/', users_list, name='users_list'),
 path('users/toggle-block/', toggle_block_user, name='toggle_block_user'),
 path('', admin_login, name='admin_login'),
]

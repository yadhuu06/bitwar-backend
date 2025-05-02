from django.urls import path
from .views import UsersListView, ToggleBlockUserView, AdminLoginView, RoomListView

urlpatterns = [
    path('', AdminLoginView.as_view(), name='admin_login'),
    path('users/toggle-block/', ToggleBlockUserView.as_view(), name='toggle_block_user'),
    path('users_list/', UsersListView.as_view(), name='users_list'),
    path('battles/', RoomListView.as_view(), name='battle-list'),
]
from django.urls import path
from . import views 

urlpatterns = [
    path('',views. AdminLoginView.as_view(), name='admin_login'),
    path('users/toggle-block/', views.ToggleBlockUserView.as_view(), name='toggle_block_user'),
    path('users_list/', views.UsersListView.as_view(), name='users_list'),
    path('battles/', views.RoomListView.as_view(), name='battle-list'),
    path('dashboard/',views.AdminDashboardView.as_view(), name='admin_dashboard'),
    
]
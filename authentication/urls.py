from django.urls import path
from .views import (
    register_view, login_view, profile_view,
    GenerateOTPView, VerifyOTPView, RegisterCompleteView,
    admin_dashboard_view, GoogleLoginCallback, logout_view, user_dashboard_view
)

urlpatterns = [
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('profile/', profile_view, name='profile'),
    path('otp/generate/', GenerateOTPView.as_view(), name='generate_otp'),
    path('otp/verify/', VerifyOTPView.as_view(), name='verify_otp'),
    path('register/complete/', RegisterCompleteView.as_view(), name='register_complete'),
    path('user-dashboard/', user_dashboard_view, name='user_dashboard'),
    path('admin-dashboard/', admin_dashboard_view, name='admin_dashboard'),
    path('google/callback/', GoogleLoginCallback.as_view(), name='google_callback'),
    path('logout/', logout_view, name='logout_view'),
]
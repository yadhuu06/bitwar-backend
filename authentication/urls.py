# authentication/urls.py
from django.urls import path
from .views import (
    register_view, login_view, profile_view,
    GenerateOTPView, VerifyOTPView, RegisterCompleteView
)

urlpatterns = [
    # Function-based views
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('profile/', profile_view, name='profile'),
    
    # Class-based OTP views
    path('otp/generate/', GenerateOTPView.as_view(), name='generate_otp'),
    path('otp/verify/', VerifyOTPView.as_view(), name='verify_otp'),
    path('register/complete/', RegisterCompleteView.as_view(), name='register_complete'),
]
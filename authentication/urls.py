from django.urls import path
from authentication import views

urlpatterns = [
    path('otp/generate/', views.GenerateOTPView.as_view(), name='generate_otp'),
    path('otp/verify/', views.VerifyOTPView.as_view(), name='verify_otp'),
    path('password/reset/', views.PasswordResetView.as_view(), name='password_reset'),
    path('register/complete/', views.RegisterCompleteView.as_view(), name='register_complete'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('google/callback/', views.GoogleLoginCallbackView.as_view(), name='google_callback'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('dashboard/', views.UserDashboardView.as_view(), name='user_dashboard'),
    path('dashboard/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('imagekit/', views.ImageKitAuthView.as_view(), name='imagekit-auth')
    
]
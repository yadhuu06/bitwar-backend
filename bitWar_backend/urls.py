from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from authentication.views import GoogleLoginCallback
urlpatterns = [
    path('api/auth/', include('authentication.urls')),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('social-auth/', include('social_django.urls', namespace='social')),
   
    path('admin-panel/', include('admin_panel.urls')),
]

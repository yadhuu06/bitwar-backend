from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from authentication.views import GoogleLoginCallback
from django.conf.urls.static import static
from django.conf import settings
urlpatterns = [
    path('api/auth/', include('authentication.urls')),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('social-auth/', include('social_django.urls', namespace='social')),
    
   path('social-auth/complete/google-oauth2/', GoogleLoginCallback.as_view(), name='social_complete'), 
    path('admin-panel/', include('admin_panel.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
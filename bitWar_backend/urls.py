from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from authentication.views import GoogleLoginCallback
from django.conf.urls.static import static
from django.conf import settings


urlpatterns = [
    path('api/auth/', include('authentication.urls')),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('admin-panel/', include('admin_panel.urls')),
    path('rooms/', include('room.urls')),
    path('questions/', include('problems.urls')),
    path('battle/',include('battle.urls'))

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


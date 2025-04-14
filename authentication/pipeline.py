from django.contrib.auth import get_user_model, login
from django.conf import settings
from social_core.pipeline.user import get_username as social_get_username
from social_core.exceptions import AuthException
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

def get_username(strategy, details, user=None, *args, **kwargs):
    """Generate a unique username from email."""
    if user:
        return {'username': user.username}
    email = details.get('email')
    if not email:
        return None
    username = email.split('@')[0]
    base_username = username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1
    return {'username': username}

def associate_or_create_user(backend, details, response, request, *args, **kwargs):
    """Associate or create a user for social auth and return tokens."""
    email = details.get('email') or response.get('email')
    if not email:
        raise AuthException(backend, "Email not provided by social provider.")

    try:
        user = User.objects.get(email=email)
        is_new = False
    except User.DoesNotExist:
        username = get_username(backend.strategy, details)['username']
        user = User.objects.create_user(
            email=email,
            username=username,
            auth_type='google',
        )
        user.set_unusable_password()
        user.save()
        is_new = True

    uid = response.get('sub')
    if not uid:
        raise AuthException(backend, "No user ID ('sub') found in response.")

    social_user = backend.strategy.storage.user.get_social_auth(
        provider=backend.name, uid=uid
    )
    if not social_user:
        backend.strategy.storage.user.create_social_auth(
            user=user, uid=uid, provider=backend.name
        )

    user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, user)

    refresh = RefreshToken.for_user(user)

    frontend_base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
    redirect_url = f"{frontend_base_url}/admin/dashboard" if user.is_superuser else f"{frontend_base_url}/user/dashboard"
    response_data = {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'role': 'admin' if user.is_superuser else 'user',
        'redirect_url': redirect_url
    }

    return {
        'user': user,
        'is_new': is_new,
        'redirect_to': response_data['redirect_url']
    }

def user_details(strategy, details, user, *args, **kwargs):
    """Update user details from social provider."""
    if not user:
        return
    updated = False
    new_email = details.get('email', user.email)
    new_username = details.get('username', user.username)
    if user.email != new_email:
        user.email = new_email
        updated = True
    if user.username != new_username:
        user.username = new_username
        updated = True
    if updated:
        user.save()
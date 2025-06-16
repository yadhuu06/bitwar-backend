from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed

class WebSocketAuthMixin:
    @database_sync_to_async
    def get_user_from_token(self, token):
        try:
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            user = jwt_auth.get_user(validated_token)
            return user
        except AuthenticationFailed:
            return None
        except Exception as e:
            print(f"[ERROR] Token validation failed: {str(e)}")
            return None

    async def authenticate_user(self, query_string):
        token = None
        for param in query_string.decode().split('&'):
            if param.startswith('token='):
                token = param[len('token='):]
                break
        if not token:
            await self.close(code=4001, reason="No token provided")
            return None

        user = await self.get_user_from_token(token)
        if user is None or isinstance(user, AnonymousUser):
            await self.close(code=4002, reason="Invalid or expired token")
            return None

        return user
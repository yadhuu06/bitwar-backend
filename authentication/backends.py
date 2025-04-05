# authentication/backends.py
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

class EmailAuthBackend(ModelBackend):
    def authenticate(self, request, email=None, password=None, **kwargs):
        UserModel = get_user_model()
        if email is None:
            print("No email provided")
            return None

        print(f"Looking up user with email: {email}")
        try:
            user = UserModel.objects.get(email=email)
            print(f"User found: {user.email}, is_active: {user.is_active}")
        except UserModel.DoesNotExist:
            print(f"No user found with email: {email}")
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            print("Password check passed")
            return user
        print("Password check failed")
        return None
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone

class CustomUserManager(BaseUserManager):
    """Manager for creating CustomUser instances."""
    def create_user(self, email, username, password=None, **extra_fields):
        """Create and save a regular user with the given email, username, and password."""
        if not email:
            raise ValueError('The Email field must be set')
        if not username:
            raise ValueError('The Username field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        """Create and save a superuser with the given email, username, and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(email, username, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    """Custom user model with email as the primary identifier."""
    AUTH_TYPE_CHOICES = (
        ('manual', 'Manual'),
        ('google', 'Google'),
        ('github', 'GitHub'),
    )

    user_id = models.AutoField(primary_key=True)
    email = models.EmailField(unique=True, db_index=True)  # Indexed for fast lookups
    username = models.CharField(max_length=150, unique=True, db_index=True)  # Indexed for fast lookups
    created_at = models.DateTimeField(default=timezone.now, db_index=True)  # Indexed for ordering/filtering
    updated_at = models.DateTimeField(auto_now=True)
    auth_type = models.CharField(max_length=10, choices=AUTH_TYPE_CHOICES, default='manual')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'  # Login with email
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.username

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['email', 'username']),  # Composite index for common queries
        ]
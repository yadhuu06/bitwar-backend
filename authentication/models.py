from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.db import models
from django.utils import timezone
from cryptography.fernet import Fernet
from django.conf import settings

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
    email = models.EmailField(unique=True, db_index=True)  
    username = models.CharField(max_length=150, unique=True, db_index=True)  
    created_at = models.DateTimeField(default=timezone.now, db_index=True)  
    updated_at = models.DateTimeField(auto_now=True)
    auth_type = models.CharField(max_length=10, choices=AUTH_TYPE_CHOICES, default='manual')
    is_active = models.BooleanField(default=True)
    is_blocked = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'  
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.username

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['email', 'username']),  # Composite index for common queries
        ]

from django.db import models
from django.utils import timezone
from cryptography.fernet import Fernet
from django.conf import settings

# Generate encryption key once and store in settings (move to settings.py ideally)
ENCRYPTION_KEY = getattr(settings, 'FERNET_KEY', Fernet.generate_key())  
FERNET = Fernet(ENCRYPTION_KEY)

class OTP(models.Model):
    email = models.EmailField(unique=True)
    otp_encrypted = models.BinaryField()  
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False) 

    def save(self, *args, **kwargs):
        if not self.expires_at:
  
            self.expires_at = timezone.now() + timezone.timedelta(minutes=1)
        super().save(*args, **kwargs)

    def set_otp(self, otp):
        """Encrypt OTP before saving"""
        # Ensure OTP is a string and encode it to bytes before encryption
        otp_bytes = str(otp).encode('utf-8')
        self.otp_encrypted = FERNET.encrypt(otp_bytes)  

        self.is_verified = False
        self.expires_at = timezone.now() + timezone.timedelta(minutes=1)
        self.save()  

    def get_otp(self):
        """Decrypt OTP for verification"""
        if not self.otp_encrypted:
            return None

        # Handle different possible types from BinaryField
        token = self.otp_encrypted
        if isinstance(token, memoryview):
            token = bytes(token)  
        elif isinstance(token, str):
            token = token.encode('utf-8')  
        elif not isinstance(token, bytes):
            raise TypeError(f"otp_encrypted must be bytes, got {type(token)}")

        try:
            decrypted_otp = FERNET.decrypt(token).decode('utf-8')
            return decrypted_otp
        except Exception as e:
            print(f"Error decrypting OTP: {e}")
            return None

    def is_expired(self):
        """Check if OTP has expired"""
        return timezone.now() > self.expires_at

    def mark_verified(self):
        """Mark OTP as verified after successful verification"""
        self.is_verified = True
        self.save()

    class Meta:
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['is_verified']),
        ]

    def __str__(self):
        return f"OTP for {self.email} (Verified: {self.is_verified})"
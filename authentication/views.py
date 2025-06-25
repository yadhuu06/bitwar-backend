import logging
import json
from random import randint
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import authenticate, get_user_model
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.exceptions import TokenError
from social_django.utils import psa
from decouple import config
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from .models import OTP, CustomUser
from .serializers import OTPSerializer, RegisterSerializer, UserSerializer
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

CustomUser = get_user_model()

class OTPThrottle(AnonRateThrottle):
    rate = '10/hour'

def generate_auth_response(user):
    refresh = RefreshToken.for_user(user)
    redirect_path = '/user/dashboard' if not user.is_superuser else '/admin/dashboard'
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'role': 'admin' if user.is_superuser else 'user',
        'username': user.username,
        'redirect_url': redirect_path
    }

class GenerateOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OTPThrottle]

    def post(self, request):
        serializer = OTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        otp_type = serializer.validated_data['otp_type']

        otp = str(randint(100000, 999999))
        otp_instance = OTP.objects.filter(email=email).first()

        if otp_instance:
            time_since_last_sent = (timezone.now() - otp_instance.created_at).total_seconds()
            if time_since_last_sent < 120:
                remaining_cooldown = int(120 - time_since_last_sent)
                return Response({
                    'error': f'Please wait {remaining_cooldown} seconds before requesting a new OTP'
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)

            if otp_type == 'registration' and CustomUser.objects.filter(email=email).exists():
                CustomUser.objects.filter(email=email).delete()

        if otp_instance:
            otp_instance.set_otp(otp)
            otp_instance.is_verified = False
            otp_instance.otp_type = otp_type
        else:
            otp_instance = OTP.objects.create(email=email, is_verified=False, otp_type=otp_type)
            otp_instance.set_otp(otp)

        otp_instance.save()
        logger.info(f"Generated OTP for {email}: {otp}")

        subject = '🔐 < Bit Code > Email Verification - OTP Inside' if otp_type == 'registration' else '🔐 < Bit Code > Password Reset - OTP Inside'
        html_message = render_to_string('emails/otp_verification.html', {'otp': otp, 'otp_type': otp_type})
        plain_message = f'Your OTP is: {otp}. Valid for 10 minutes.'

        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html_message,
                fail_silently=False,
            )
            logger.info(f"Email sent to {email}")
        except Exception as e:
            logger.error(f"Email sending failed: {str(e)}")
            return Response({'error': 'Failed to send OTP', 'details': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        expiration_time = int((otp_instance.expires_at - timezone.now()).total_seconds())
        return Response({
            'message': 'OTP sent successfully',
            'expires_in': expiration_time
        }, status=status.HTTP_200_OK)

import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

class VerifyOTPView(APIView):
    throttle_classes = [OTPThrottle]
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp_input = request.data.get('otp')
        
        if not email or not otp_input:
            return Response({'error': 'Email and OTP are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            otp_instance = OTP.objects.get(email=email)

            if otp_instance.is_expired():
                otp_instance.delete()
                return Response({'error': 'OTP expired'}, status=status.HTTP_400_BAD_REQUEST)            
            if otp_instance.get_otp() != otp_input:
                return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)
            

            otp_instance.mark_verified()

            return Response({'message': 'OTP verified successfully'}, status=status.HTTP_200_OK)

        except OTP.DoesNotExist:
            return Response({'error': 'No OTP found for this email'}, status=status.HTTP_404_NOT_FOUND)

class PasswordResetView(APIView):
    throttle_classes = [OTPThrottle]
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        new_password = request.data.get('new_password')

        if not all([email, otp, new_password]):
            return Response({'error': 'Email, OTP, and new password are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = CustomUser.objects.get(email=email, is_active=True)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found or inactive'}, status=status.HTTP_404_NOT_FOUND)

        try:
            otp_instance = OTP.objects.get(
                email=email,
                is_verified=False,
                otp_type='forgot_password',
                expires_at__gt=timezone.now()
            )
        except OTP.DoesNotExist:
            return Response({'error': 'Invalid or expired OTP'}, status=status.HTTP_400_BAD_REQUEST)

        decrypted_otp = otp_instance.get_otp()
        if not decrypted_otp or decrypted_otp != otp:
            return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)

        if len(new_password) < 8 or not any(c.isupper() for c in new_password) or not any(c in '!@#$%^&*(),.?":{}|<>' for c in new_password):
            return Response({'error': 'Password must be 8+ chars, include 1 uppercase and 1 special char'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        otp_instance.mark_verified()

        return Response({'success': True, 'message': 'Password reset successfully'}, status=status.HTTP_200_OK)

class RegisterCompleteView(APIView):
    throttle_classes = [OTPThrottle]
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            otp_record = OTP.objects.get(email=email)
            if not otp_record.is_verified:
                return Response({'error': 'Email verification not completed'}, status=status.HTTP_400_BAD_REQUEST)
        except OTP.DoesNotExist:
            return Response({'error': 'Email verification not found'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            otp_record.delete()
            return Response(generate_auth_response(user), status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User registered successfully. Check email for OTP."}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        if not email or not password:
            return Response({"error": "Email and password are required"}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, email=email, password=password)
        if user:
            if user.is_blocked:
                return Response({"error": "User IS Blocked By Admin"}, status=status.HTTP_401_UNAUTHORIZED)
            user.last_login = timezone.now()
            user.save()
            return Response(generate_auth_response(user), status=status.HTTP_200_OK)
        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

class GoogleLoginCallbackView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        google_credential = request.data.get('credential')
        logger.debug(f"Received Google credential: {google_credential}")

        if not google_credential:
            logger.error("No credential received")
            return Response({"error": "No credential received"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client_id = config('GOOGLE_CLIENT_ID')
            token_info = id_token.verify_oauth2_token(google_credential, google_requests.Request(), client_id)
            logger.debug(f"Token info: {token_info}")
        except ValueError as e:
            logger.error(f"Failed to validate ID token: {str(e)}")
            return Response({"error": f"Failed to verify credential: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        if "email" not in token_info:
            logger.error("No email in token info")
            return Response({"error": "Failed to retrieve user information"}, status=status.HTTP_400_BAD_REQUEST)

        email = token_info["email"]
        user, created = CustomUser.objects.get_or_create(
            email=email,
            defaults={
                "username": email,
                "profile_picture": token_info.get("picture", ""),
                "is_active": True,
                "auth_type": "google",
            },
        )
        if not created:
            user.profile_picture = token_info.get("picture", user.profile_picture)
            user.is_active = True
            user.auth_type = "google"
            user.save()

        response_data = {
            "message": "Login successful",
            "user": {
                "id": user.user_id,
                "email": user.email,
                "username": user.username,
                "is_superuser": user.is_superuser,
            },
            "access_token": str(RefreshToken.for_user(user).access_token),
            "refresh_token": str(RefreshToken.for_user(user)),
        }
        logger.debug(f"Response data: {response_data}")
        return Response(response_data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            if not refresh_token:
                logger.warning("Logout attempted without refresh token")
                return Response({"error": "Refresh token required"}, status=status.HTTP_400_BAD_REQUEST)

            logger.info(f"Logout request with refresh token: {refresh_token}")
            token = RefreshToken(refresh_token)
            token.blacklist()
            logger.info("User successfully logged out")
            return Response({"message": "Successfully logged out"}, status=status.HTTP_200_OK)
        except TokenError as e:
            logger.error(f"Token error during logout: {str(e)}")
            return Response({"error": "Invalid refresh token"}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.error(f"Unexpected error during logout: {str(e)}")
            return Response({"error": "Logout failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = UserSerializer(user)
        return Response({
            'message': f"Welcome to the User Dashboard, {user.email}!",
            'user': serializer.data
        }, status=status.HTTP_200_OK)

class AdminDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not user.is_superuser:
            return Response({"error": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)
        return Response({
            'message': f"Welcome to the Admin Dashboard, {user.email}!",
            'email': user.email,
            'username': user.username,
            'role': 'admin',
        }, status=status.HTTP_200_OK)

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        user = request.user
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
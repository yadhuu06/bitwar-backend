import logging
from random import randint
from datetime import timedelta
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.http import HttpResponse
from django.contrib.auth import authenticate, get_user_model
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from rest_framework_simplejwt.exceptions import TokenError
from social_django.utils import psa
from decouple import config
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from .models import OTP, CustomUser
from .serializers import OTPSerializer, RegisterSerializer, UserSerializer
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

Accounts = get_user_model()


class OTPThrottle(AnonRateThrottle):
    rate = '10/hour'

def generate_auth_response(user):
  
    refresh = RefreshToken.for_user(user)
    frontend_base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
    redirect_path = '/user/dashboard' if not user.is_superuser else '/admin/dashboard'
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'role': 'admin' if user.is_superuser else 'user',
        'redirect_url': redirect_path
    }




class GenerateOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        """Generate and send OTP for email verification."""
        serializer = OTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        if CustomUser.objects.filter(email=email).exists():
            return Response({'error': 'Email already registered'}, status=status.HTTP_400_BAD_REQUEST)

        # Generate OTP
        otp = str(randint(100000, 999999))
        otp_instance = OTP.objects.filter(email=email).first()

        # Check resend cooldown (2 minutes)
        if otp_instance and otp_instance.last_sent_at:
            time_since_last_sent = (timezone.now() - otp_instance.last_sent_at).total_seconds()
            if time_since_last_sent < 120:
                remaining_cooldown = int(120 - time_since_last_sent)
                return Response({
                    'error': f'Please wait {remaining_cooldown} seconds before requesting a new OTP'
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Create or update OTP instance
        if otp_instance:
            otp_instance.set_otp(otp)
            otp_instance.is_verified = False
        else:
            otp_instance = OTP.objects.create(email=email, is_verified=False)
            otp_instance.set_otp(otp)

        otp_instance.save()
        print(f"Generated OTP for {email}: {otp}")  # Debug

        # Email content
        subject = '🔐 < Bit Code > Email Verification - OTP Inside'
        plain_message = f'Your OTP is: {otp}. Valid for 10 minutes.'

        html_message = render_to_string('emails/otp_verification.html', {'otp': otp})
        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html_message,
                fail_silently=False,
            )
            print(f"Email sent to {email}")  # Debug
        except Exception as e:
            print(f"Email sending failed for {email}: {str(e)}")  # Debug
            return Response(
                {'error': 'Failed to send OTP', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        expiration_time = int((otp_instance.expires_at - timezone.now()).total_seconds())
        return Response({
            'message': 'OTP sent successfully',
            'expires_in': expiration_time
        }, status=status.HTTP_200_OK)
    


class VerifyOTPView(APIView):
    throttle_classes = [OTPThrottle]
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        print(email)
        otp_input = request.data.get('otp')
        if not email or not otp_input:
            return Response({'error': 'Email and OTP are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            otp_instance = OTP.objects.get(email=email)
            if otp_instance.is_expired():
                return Response({'error': 'OTP expired'}, status=status.HTTP_400_BAD_REQUEST)
            if otp_instance.get_otp() != otp_input:
                return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)
            otp_instance.mark_verified()
            return Response({'message': 'OTP verified successfully'}, status=status.HTTP_200_OK)
        except OTP.DoesNotExist:
            return Response({'error': 'No OTP found for this email'}, status=status.HTTP_404_NOT_FOUND)


class RegisterCompleteView(APIView):
    throttle_classes = [OTPThrottle]
    permission_classes = [AllowAny]
    def post(self, request):
        print("Incoming data:", request.data)

        print("call came")
        email = request.data.get('email')
        if not email:
            print("no email")
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            otp_record = OTP.objects.get(email=email)
            if not otp_record.is_verified:
                print("otp not there verified")
                return Response({'error': 'Email verification not completed'}, status=status.HTTP_400_BAD_REQUEST)
        except OTP.DoesNotExist:
            return Response({'error': 'Email verification not found'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            otp_record.delete()
            return Response(generate_auth_response(user), status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def register_view(request):
    """Register a new user and initiate OTP verification."""
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({"message": "User registered successfully. Check email for OTP."}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def login_view(request):
    """Authenticate user and return tokens."""
    email = request.data.get('email')
    password = request.data.get('password')
    if not email or not password:
        return Response({"error": "Email and password are required"}, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(request, email=email, password=password)
    if user:
        if user.is_blocked:
            return Response({"error": "User IS Blocked By Admin"}, status=status.HTTP_401_UNAUTHORIZED)
        user.last_login=timezone.now()
        user.save()
        return Response(generate_auth_response(user), status=status.HTTP_200_OK)
    return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)



class GoogleLoginCallback(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        google_credential = request.data.get('credential')
        logger.debug(f"Received Google credential: {google_credential}")

        if not google_credential:
            logger.error("No credential received")
            return Response(
                {"error": "No credential received"},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            client_id = config('GOOGLE_CLIENT_ID') 
            token_info = id_token.verify_oauth2_token(
                google_credential,
                google_requests.Request(),
                client_id
            )
            logger.debug(f"Token info: {token_info}")
        except ValueError as e:
            logger.error(f"Failed to validate ID token: {str(e)}")
            return Response(
                {"error": f"Failed to verify credential: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if "email" not in token_info:
            logger.error("No email in token info")
            return Response(
                {"error": "Failed to retrieve user information"},
                status=status.HTTP_400_BAD_REQUEST
            )

        email = token_info["email"]


        user, created = Accounts.objects.get_or_create(
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

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        response_data = {
            "message": "Login successful",
            "user": {
                "id": user.user_id,
                "email": user.email,
                "username": user.username,
                "is_superuser": user.is_superuser,
            },
            "access_token": str(access),
            "refresh_token": str(refresh),
        }

        logger.debug(f"Response data: {response_data}")
        return Response(response_data, status=status.HTTP_200_OK)



logger = logging.getLogger(__name__)

@csrf_exempt  # Exempt from CSRF protection
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    print("data=", request.data)

    try:
        refresh_token = request.data.get('refresh_token')
        if not refresh_token:
            logger.warning("Logout attempted without refresh token in request body")
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


def user_dashboard_view(request):
    """Render user dashboard."""
    return HttpResponse("Hai")

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_dashboard_view(request):
    """Render admin dashboard for superusers."""
    user = request.user
    if not user.is_superuser:
        return Response({"error": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    return Response({
        'message': f"Welcome to the Admin Dashboard, {user.email}!",
        'email': user.email,
        'username': user.username,
        'role': 'admin',
    }, status=status.HTTP_200_OK)

@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    """View or update user profile."""
    user = request.user
    if request.method == 'GET':
        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)
    elif request.method == 'PATCH':
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
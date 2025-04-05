from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, login
from django.core.mail import send_mail
from django.utils.crypto import get_random_string
from rest_framework.views import APIView
from rest_framework.throttling import AnonRateThrottle
from django.conf import settings
from django.utils import timezone
from social_django.utils import psa
from .models import OTP, CustomUser
from .serializers import OTPSerializer, RegisterSerializer, UserSerializer
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from rest_framework_simplejwt.exceptions import TokenError
import logging


class OTPThrottle(AnonRateThrottle):
    rate = '10/hour' 


def generate_auth_response(user):

    refresh = RefreshToken.for_user(user)
    redirect_url = '/api/auth/admin-dashboard/' if user.is_superuser else '/api/auth/user-dashboard/'
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'role': 'admin' if user.is_superuser else 'user',
        'redirect_url': redirect_url
    }

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt 
def register_view(request):

    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({"message": "User registered successfully"}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])  
@csrf_exempt  
def login_view(request):

    email = request.data.get('email')
    password = request.data.get('password')
    if not email or not password:
        return Response({"error": "Email and password are required"}, status=status.HTTP_400_BAD_REQUEST)
    
    user = authenticate(request, email=email, password=password)
    if user:
        return Response(generate_auth_response(user), status=status.HTTP_200_OK)
    return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

# User profile view
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_view(request):

    serializer = UserSerializer(request.user)
    return Response(serializer.data, status=status.HTTP_200_OK)

# User dashboard
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_dashboard_view(request):

    user = request.user
    return Response({
        'message': f"Welcome to the User Dashboard, {user.email}!",
        'email': user.email,
        'username': user.username,
        'role': 'user',
    }, status=status.HTTP_200_OK)

# Admin dashboard
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_dashboard_view(request):

    user = request.user
    if not user.is_superuser:
        return Response({"error": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    return Response({
        'message': f"Welcome to the Admin Dashboard, {user.email}!",
        'email': user.email,
        'username': user.username,
        'role': 'admin',
    }, status=status.HTTP_200_OK)

# Generate OTP for email verification
class GenerateOTPView(APIView):
    throttle_classes = [OTPThrottle]
    permission_classes = [AllowAny]

    def post(self, request):
     
        serializer = OTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        if CustomUser.objects.filter(email=email).exists():
            return Response({'error': 'Email already registered'}, status=status.HTTP_400_BAD_REQUEST)

        otp = get_random_string(length=6, allowed_chars='0123456789')
        otp_instance, _ = OTP.objects.update_or_create(
            email=email, defaults={'otp': otp, 'is_verified': False}
        )

        try:
            send_mail(
                'Your Bit Code Verification Code',
                f'Your verification code is: {otp}\nValid for 1 minute.',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
        except Exception as e:
            return Response({'error': 'Failed to send OTP'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        expiration_time = int((otp_instance.expires_at - timezone.now()).total_seconds())
        return Response({
            'message': 'OTP sent successfully',
            'expires_in': expiration_time
        }, status=status.HTTP_200_OK)


class VerifyOTPView(APIView):
    throttle_classes = [OTPThrottle]
    permission_classes = [AllowAny]

    def post(self, request):
        """Verify the OTP for the given email."""
        email = request.data.get('email')
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
        """Complete registration after OTP verification."""
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


class GoogleLoginCallback(APIView):
    @psa('social:complete')
    def get(self, request, backend):
 
        user = request.backend.do_auth(request.GET.get('code'))
        if user:
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            response_data = generate_auth_response(user)

            response_data['redirect_url'] = (
                f"http://localhost:3000/auth/callback?"
                f"access_token={response_data['access']}&"
                f"refresh_token={response_data['refresh']}&"
                f"email={user.email}&"
                f"username={user.username}"
            )
            return Response(response_data, status=status.HTTP_200_OK)
        return Response({'error': 'Authentication failed'}, status=status.HTTP_400_BAD_REQUEST)
    
    
def logout_view(request):
    print()


logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated]) 
def logout_view(request):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        logger.warning("Logout attempted without valid Authorization header")
        return Response({"error": "Authorization header missing or invalid"}, status=status.HTTP_401_UNAUTHORIZED)

    token = auth_header.split(' ')[1]
    logger.info(f"Logout request with token: {token}")

    try:
        # Optionally blacklist the token
        refresh_token = RefreshToken(token)
        refresh_token.blacklist()  # Blacklist the refresh token
        logger.info("User successfully logged out")
        return Response({"message": "Successfully logged out"}, status=status.HTTP_200_OK)
    except TokenError as e:
        logger.error(f"Token error during logout: {str(e)}")
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)
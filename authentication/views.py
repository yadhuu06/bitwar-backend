# authentication/views.py
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.utils.crypto import get_random_string
from rest_framework.views import APIView
from rest_framework.throttling import AnonRateThrottle
from django.conf import settings
from .models import OTP, CustomUser
from .serializers import OTPSerializer, RegisterSerializer, UserSerializer

# Function-based views for JWT authentication
@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({"message": "User registered successfully"}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    email = request.data.get('email')
    password = request.data.get('password')
    if not email or not password:
        return Response({"error": "Email and password are required"}, status=status.HTTP_400_BAD_REQUEST)
    
    user = authenticate(request, email=email, password=password)
    if user is not None:
        refresh = RefreshToken.for_user(user)
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_200_OK)
    return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data, status=status.HTTP_200_OK)

# Class-based views for OTP-based registration
class OTPThrottle(AnonRateThrottle):
    rate = '10/hour'  # Limit to 10 requests per hour per IP

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

        # Generate 6-digit OTP
        otp = get_random_string(length=6, allowed_chars='0123456789')
        
        # Store OTP securely
        otp_instance, created = OTP.objects.get_or_create(email=email)
        otp_instance.set_otp(otp)
        otp_instance.save()

        # Send OTP via email
        try:
            send_mail(
                'Your OTP Code',
                f'Your verification code is: {otp}\nValid for 1 minute.',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
        except Exception as e:
            return Response({'error': 'Failed to send OTP'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'message': 'OTP sent successfully'})

class VerifyOTPView(APIView):
    throttle_classes = [OTPThrottle]
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp_input = request.data.get('otp')
        
        try:
            otp_instance = OTP.objects.get(email=email)
            if otp_instance.is_expired():
                otp_instance.delete()
                return Response({'error': 'OTP expired'}, status=status.HTTP_400_BAD_REQUEST)
            
            if otp_instance.get_otp() != otp_input:
                return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({'message': 'OTP verified'})
        except OTP.DoesNotExist:
            return Response({'error': 'No OTP found'}, status=status.HTTP_404_NOT_FOUND)

class RegisterCompleteView(APIView):
    throttle_classes = [OTPThrottle]
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            # Generate JWT tokens upon registration
            refresh = RefreshToken.for_user(user)
            return Response({
                'message': 'Registration successful',
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    




from django.core.mail import send_mail

def send_test_email():
    subject = 'Welcome to Bitcode - Test Message'
    message = 'Hello! This is a test email from Bitcode Official to confirm our email system is working.'
    from_email = 'Bitcode Official <bitcodeofficial01@gmail.com>'
    recipient_list = ['yadhuu.ps@gmail.com']  
    try:
        send_mail(subject, message, from_email, recipient_list, fail_silently=False)
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")
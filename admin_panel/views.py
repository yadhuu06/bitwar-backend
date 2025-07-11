from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from authentication.models import CustomUser
from room.models import Room
from .serializers import RoomSerializer
from .serializers import UserSerializer
from problems.models import Question
from room.models import Room
from authentication. models import CustomUser
from battle.models import UserRanking
from . serializers import UserRankingSerializer



class UsersListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        users = CustomUser.objects.filter(is_superuser=False)
        serializer = UserSerializer(users, many=True)
        return Response({
            'users': serializer.data,
            'message': 'Users retrieved successfully',
            'method': request.method
        }, status=status.HTTP_200_OK)

class ToggleBlockUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        try:
            user_id = request.data.get('user_id')
            if not user_id:
                return Response({'error': 'User ID is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            user = get_object_or_404(CustomUser, user_id=user_id)
            user.is_blocked = not user.is_blocked
            user.save()
            
            return Response({
                'message': f'User {"unblocked" if not user.is_blocked else "blocked"} successfully',
                'is_blocked': user.is_blocked
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AdminLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            email = request.data.get('email', '').strip()
            password = request.data.get('password', '').strip()

            if not email or not password:
                return Response({"error": "Email and password are required"}, status=status.HTTP_400_BAD_REQUEST)

            user = authenticate(request, username=email, password=password)
            if not user:
                return Response({"error": "Invalid email or password"}, status=status.HTTP_401_UNAUTHORIZED)

            if not user.is_superuser:
                return Response({"error": "Access denied. Not an admin."}, status=status.HTTP_403_FORBIDDEN)

            refresh = RefreshToken.for_user(user)
            return Response({
                "message": "Login successful",
                "admin_id": str(user.user_id),
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

class RoomListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        rooms = Room.objects.all()
        serializer = RoomSerializer(rooms, many=True)
        return Response({'battles': serializer.data}, status=status.HTTP_200_OK)
    
    
class AdminDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        user = request.user
        if not user.is_superuser:
            return Response({"error": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)

        active_rooms = Room.objects.filter(status='active').count()
        active_matches = Room.objects.filter(status='playing').count()
        active_questions = Question.objects.filter(is_validate=True).count()
        total_users = CustomUser.objects.filter(is_blocked=False).count()
        top_5_ranks = UserRanking.objects.select_related('user').order_by('-points')[:5]

        serialized_top_users = UserRankingSerializer(top_5_ranks, many=True).data

        return Response({
            'message': f"Welcome to the Admin Dashboard, {user.email}!",
            'active_matches': active_matches,
            'active_questions': active_questions,
            'active_rooms': active_rooms,
            'total_users': total_users,
            'top_users': serialized_top_users
        }, status=status.HTTP_200_OK)

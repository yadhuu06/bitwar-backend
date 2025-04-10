from authentication.models import CustomUser  
from django.views.decorators.csrf import csrf_exempt
import json
from django.http import JsonResponse



def users_list(request):
    if request.method == 'GET':
        users = CustomUser.objects.filter(is_superuser=False)

        users_data = [
            {
                'id': user.user_id,  
                'username': user.username,
                'email': user.email,
                'is_blocked': user.is_blocked  
            }
            for user in users
        ]
        return JsonResponse({
            'users': users_data,
            'message': 'Users retrieved successfully',
            'method': request.method
        }, status=200)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def toggle_block_user(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            if not user_id:
                return JsonResponse({'error': 'User ID is required'}, status=400)
            user = CustomUser.objects.get(user_id=user_id)  
            user.is_blocked = not user.is_blocked  
            return JsonResponse({
                'message': f'User {"unblocked" if not user.is_blocked else "blocked"} successfully',
                'is_blocked': user.is_blocked
            }, status=200)
        except CustomUser.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)



from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken


@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login(request):
    if request.method == 'POST':
        try:
            data = request.data
            email = data.get('email', '').strip()
            password = data.get('password', '').strip()

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
                "admin_id": user.user_id,  
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"error": "Method not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
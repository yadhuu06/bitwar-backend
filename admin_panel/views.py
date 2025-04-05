from authentication.models import CustomUser  # Replace with your app name
from django.views.decorators.csrf import csrf_exempt
import json
from django.http import JsonResponse



def users_list(request):
    if request.method == 'GET':
        users = CustomUser.objects.all()
        users_data = [
            {
                'id': user.user_id,  # Changed from 'id' to 'user_id' to match your model
                'username': user.username,
                'email': user.email,
                'is_blocked': user.is_blocked  # Using your custom is_blocked field
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
            user = CustomUser.objects.get(user_id=user_id)  # Changed to user_id
            user.is_blocked = not user.is_blocked  # Toggle your custom field
            user.save()
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
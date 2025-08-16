import logging
from django.utils import timezone
from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from problems.models import Question, TestCase, SolvedCode, Example
from problems.serializers import QuestionListSerializer, TestCaseSerializer, ExampleSerializer
from problems.services.judge0_service import verify_with_judge0
from problems.utils import extract_function_name_and_params

from battle.models import BattleResult, UserRanking
from rankings.utils import calculate_elo_1v1, calculate_elo_squad, calculate_elo_team
from room.models import Room

from .tasks import cleanup_room_data

logger = logging.getLogger(__name__)


class BattleQuestionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, question_id):
        try:
            question = get_object_or_404(Question, id=question_id)
            if not question:
                logger.error(f"Question not found: {question_id}")
                return Response({'error': 'Question not found'}, status=status.HTTP_404_NOT_FOUND)

            serializer = QuestionListSerializer(question)
            testcases = TestCase.objects.filter(question=question)
            example = Example.objects.filter(question=question)
            example_formatted = ExampleSerializer(example, many=True)
            testcase_serializer = TestCaseSerializer(testcases, many=True)

            solved_code = SolvedCode.objects.filter(question=question, language='python').first()
            function_details = {'function_name': '', 'parameters': []}
            
            if solved_code:
                try:
                    extracted_details = extract_function_name_and_params(solved_code.solution_code, 'python')
                    function_details = {
                        'function_name': extracted_details.get('name', ''),
                        'parameters': extracted_details.get('params', [])
                    }
                except Exception as e:
                    logger.warning(f"Failed to extract function details for question {question_id}: {str(e)}")

            logger.info(f"Fetched battle question {question_id}: {question.title}")
            return Response({
                'question': serializer.data,
                'testcases': testcase_serializer.data,
                'example': example_formatted.data,
                'function_details': function_details
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching battle question {question_id}: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


logger = logging.getLogger(__name__)

class QuestionVerifyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, question_id):
        code = request.data.get('code')
        language = request.data.get('language')
        room_id = request.data.get('room_id')

        logger.info(f"Room ID received: {room_id}")

        if not all([code, language, room_id]):
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            question = Question.objects.filter(id=question_id).first()
            if not question:
                return Response({'error': 'Question not found'}, status=status.HTTP_404_NOT_FOUND)

            room = Room.objects.filter(room_id=room_id).first()
            if not room:
                return Response({'error': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)

            if not room.start_time:
                return Response({'error': 'Battle has not started'}, status=status.HTTP_400_BAD_REQUEST)

            if room.status == 'completed':
                return Response({'error': 'Battle has already ended'}, status=status.HTTP_400_BAD_REQUEST)

            # Time limit check
            if room.time_limit > 0:
                elapsed_minutes = (timezone.now() - room.start_time).total_seconds() / 60
                if elapsed_minutes > room.time_limit:
                    room.status = 'completed'
                    room.save()
                    cleanup_room_data.apply_async((room.room_id,), countdown=5 * 60)
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f"battle_{room_id}",
                        {
                            'type': 'battle_completed',
                            'message': 'Battle ended due to time limit',
                            'winners': BattleResult.objects.filter(room=room).first().results
                                if BattleResult.objects.filter(room=room).exists() else [],
                            'room_capacity': room.capacity
                        }
                    )
                    return Response({'error': 'Time limit exceeded'}, status=status.HTTP_400_BAD_REQUEST)

            # Fetch testcases
            testcases = TestCase.objects.filter(question=question)
            if not testcases.exists():
                return Response({'error': 'No test cases available'}, status=status.HTTP_400_BAD_REQUEST)

            # Verify code
            verification_result = verify_with_judge0(code, language, testcases)
            if 'error' in verification_result:
                return Response(verification_result, status=status.HTTP_400_BAD_REQUEST)

            if verification_result.get('all_passed'):
                battle_result, _ = BattleResult.objects.get_or_create(
                    room=room,
                    question=question,
                    defaults={'results': []}
                )

                existing_results = battle_result.results
                if any(result['username'] == request.user.username for result in existing_results):
                    return Response({'message': 'You have already submitted a correct solution', 'all_passed': True}, status=status.HTTP_200_OK)

                position = len(existing_results) + 1
                battle_result.add_participant_result(
                    user=request.user,
                    position=position,
                    completion_time=timezone.now()
                )
                verification_result['position'] = position

                # ----- New Ranking / Elo system -----
                if room.is_ranked:
                    participants = list(room.participants.all())
                    if room.capacity == 2:
                        calculate_elo_1v1(room.room_id, winner_id=request.user.user_id)
                    elif 3 <= room.capacity <= 5:
                        calculate_elo_squad(room)
                    elif room.capacity >= 6:
                        calculate_elo_team(room)

                # Update user stats
                if position == 1:
                    request.user.battles_won += 1
                    request.user.last_win = timezone.now().date()
                    request.user.save()


                max_winners = {2: 1, 5: 2, 10: 3}.get(room.capacity, 1)
                if len(existing_results) + 1 >= max_winners:
                    room.status = 'completed'
                    room.save()
                    cleanup_room_data.apply_async((room.room_id,), countdown=5 * 60)
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f"battle_{room_id}",
                        {
                            'type': 'battle_completed',
                            'user': request.user.username,
                            'question_id': str(question_id),
                            'winners': battle_result.results[:max_winners],
                            'room_capacity': room.capacity,
                            'message': 'Battle Ended!'
                        }
                    )
                else:
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f"battle_{room_id}",
                        {
                            'type': 'code_verified',
                            'username': request.user.username,
                            'position': position,
                            'completion_time': timezone.now().isoformat()
                        }
                    )

            return Response(verification_result, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error verifying code for question {question_id}: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    
class GlobalRankingAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):  
        rankings = UserRanking.objects.select_related('user').order_by('-points')[:100]
        ranking_data = []
        

        for index, rank in enumerate(rankings, start=1):
            ranking_data.append({
                'rank': index,
                'username': rank.user.username,
                'points': rank.points
            })

        return Response(ranking_data)   
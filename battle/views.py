import logging
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from problems.models import Question, TestCase, SolvedCode, Example
from problems.serializers import QuestionListSerializer, TestCaseSerializer, ExampleSerializer
from problems.services.judge0_service import verify_with_judge0
from problems.utils import wrap_user_code, extract_function_name_and_params
from battle.models import BattleResult, UserRanking
from room.models import Room
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .tasks import cleanup_room_data
logger = logging.getLogger(__name__)
from . tasks import cleanup_room_data

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

class QuestionVerifyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, question_id):
        code = request.data.get('code')
        language = request.data.get('language')
        room_id = request.data.get('room_id')

        logger.info(f"Room ID received: {room_id}")

        if not all([code, language, room_id]):
            logger.error("Missing required fields in request")
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            question = Question.objects.filter(id=question_id).first()
            if not question:
                logger.error(f"Question not found: {question_id}")
                return Response({'error': 'Question not found'}, status=status.HTTP_404_NOT_FOUND)

            room = Room.objects.filter(room_id=room_id).first()
            if not room:
                logger.error(f"Room not found: {room_id}")
                return Response({'error': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)

            if not room.start_time:
                logger.error(f"Battle not started for room {room_id}")
                return Response({'error': 'Battle has not started'}, status=status.HTTP_400_BAD_REQUEST)

            if room.status == 'completed':
                logger.info(f"Battle already completed for room {room_id}")
                return Response({'error': 'Battle has already ended'}, status=status.HTTP_400_BAD_REQUEST)

            if room.time_limit > 0:
                elapsed_minutes = (timezone.now() - room.start_time).total_seconds() / 60
                if elapsed_minutes > room.time_limit:
                    room.status = 'completed'

                    room.save()
                    cleanup_room_data.apply_async((room.room_id,), countdown=5 * 60)
                    logger.info(f"Time limit exceeded for room {room_id}, marking as completed")
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f"battle_{room_id}",
                        {
                            'type': 'battle_completed',
                            'message': 'Battle ended due to time limit',
                            'winners': BattleResult.objects.filter(room=room).first().results if BattleResult.objects.filter(room=room).exists() else [],
                            'room_capacity': room.capacity
                        }
                    )
                    return Response({'error': 'Time limit exceeded'}, status=status.HTTP_400_BAD_REQUEST)

            testcases = TestCase.objects.filter(question=question)
            if not testcases:
                logger.error(f"No test cases found for question {question_id}")
                return Response({'error': 'No test cases available'}, status=status.HTTP_400_BAD_REQUEST)

            verification_result = verify_with_judge0(code, language, testcases)

            if 'error' in verification_result:
                logger.error(f"Judge0 verification failed: {verification_result['error']}")
                return Response(verification_result, status=status.HTTP_400_BAD_REQUEST)

            if verification_result['all_passed']:
                battle_result, _ = BattleResult.objects.get_or_create(
                    room=room,
                    question=question,
                    defaults={'results': []}
                )

                existing_results = battle_result.results
                if any(result['username'] == request.user.username for result in existing_results):
                    logger.info(f"User {request.user.username} already submitted for room {room_id}")
                    return Response({'message': 'You have already submitted a correct solution', 'all_passed': True}, status=status.HTTP_200_OK)

                position = len(existing_results) + 1
                battle_result.add_participant_result(
                    user=request.user,
                    position=position,
                    completion_time=timezone.now()
                )
                verification_result['position'] = position
                logger.info(f"User {request.user.username} submitted correct solution, position: {position}")

                if room.is_ranked:
                    points = self.assign_ranking_points(room.capacity, position)
                    user_ranking, _ = UserRanking.objects.get_or_create(
                        user=request.user,
                        defaults={'points': 0}
                    )
                    user_ranking.points += points
                    user_ranking.save()
                    logger.info(f"Assigned {points} points to {request.user.username} for position {position}")

                max_winners = {2: 1, 5: 2, 10: 3}.get(room.capacity, 1)
                if len(existing_results) + 1 >= max_winners:
                    room.status = 'completed'
                    room.save()
                    logger.info(f"Room {room_id} battle completed with {len(existing_results) + 1} winners")
                    channel_layer = get_channel_layer()
                    cleanup_room_data.apply_async((room.room_id,), countdown=5 * 60)
                    print("cleaning started and channel send waiting")
                    async_to_sync(channel_layer.group_send)(
                        f"battle_{room_id}",
                        {
                            'type': 'battle_completed',
                            'user': request.user.username,
                            'question_id': str(question_id),
                            'winners': battle_result.results[:max_winners],
                            'room_capacity': room.capacity,+
                            'message': 'Battle Ended!'
                        }

                    )
                    print("channel sended")
                    
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
                

            logger.info(f"Code verification {'successful' if verification_result['all_passed'] else 'failed'} for user {request.user.username} in room {room_id}")
            return Response(verification_result, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error verifying code for question {question_id}: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def assign_ranking_points(self, capacity, position):
        points_map = {
            2: {1: 50, 2: 0},
            5: {1: 70, 2: 40, 3: 0, 4: 0, 5: 0},
            10: {1: 100, 2: 60, 3: 40, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0}
        }
        return points_map.get(capacity, {1: 50}).get(position, 0)
    


class GlobalRankingAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):  
        rankings = UserRanking.objects.select_related('user').order_by('-points')[:100]
        ranking_data = []
        for i in ranking_data:
            print("data---------",i)

        for index, rank in enumerate(rankings, start=1):
            ranking_data.append({
                'rank': index,
                'username': rank.user.username,
                'points': rank.points
            })

        return Response(ranking_data)
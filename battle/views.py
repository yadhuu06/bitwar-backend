import logging
from django.utils import timezone
from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from problems.models import Question, TestCase, SolvedCode
from problems.serializers import QuestionListSerializer, TestCaseSerializer
from problems.services.judge0_service import verify_with_judge0
from problems.utils import wrap_user_code, extract_function_name_and_params

from battle.models import BattleResult, UserRanking
from room.models import Room

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)




class BattleQuestionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, question_id):
        print("url successsssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssss")
        print("question id: ",question_id)
        try:
            question = get_object_or_404(Question, id=question_id)
            if not question:
                logger.error(f"Question not found: {question_id}")
                return Response({'error': 'Question not found'}, status=status.HTTP_404_NOT_FOUND)

            serializer = QuestionListSerializer(question)
            testcases = TestCase.objects.filter(question=question)
            testcase_serializer = TestCaseSerializer(testcases, many=True)


            solved_code = SolvedCode.objects.filter(question=question, language='python').first()
            function_details = {'function_name': '', 'parameters': []}
            
            if solved_code:
                try:
                    function_details = extract_function_name_and_params(solved_code.solution_code, 'python')
                except Exception as e:
                    logger.warning(f"Failed to extract function details for question {question_id}: {str(e)}")

            logger.info(f"Fetched battle question {question_id}: {question.title}")
            return Response({
                'question': serializer.data,
                'testcases': testcase_serializer.data,
                'function_details': {
                    'function_name': function_details['name'],
                    'parameters': function_details['params']
                }
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

                # Check if user already submitted
                existing_results = battle_result.results
                if any(result['username'] == request.user.username for result in existing_results):
                    logger.info(f"User {request.user.username} already submitted for room {room_id}")
                    return Response({'message': 'You have already submitted a correct solution'}, status=status.HTTP_200_OK)

                # Determine position
                position = len(existing_results) + 1

                # Add participant result
                battle_result.add_participant_result(
                    user=request.user,
                    position=position,
                    completion_time=timezone.now()
                )

                # Assign ranking points (if ranked mode)
                if room.is_ranked:
                    points = self.assign_ranking_points(room.capacity, position)
                    user_ranking, _ = UserRanking.objects.get_or_create(
                        user=request.user,
                        defaults={'points': 0}
                    )
                    user_ranking.points += points
                    user_ranking.save()
                    logger.info(f"Assigned {points} points to {request.user.username} for position {position}")

                # Check if battle should end
                max_winners = {2: 1, 5: 3, 10: 5}.get(room.capacity, 1)
                if len(existing_results) + 1 >= max_winners:
                    room.status = 'completed'
                    room.save()
                    logger.info(f"Room {room_id} battle completed with {len(existing_results) + 1} winners")

                    # Send battle completion notification
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f"battle_{room_id}",
                        {
                            'type': 'battle_completed',
                            'user': request.user.username,
                            'question_id': str(question_id),
                            'winners': battle_result.results[:max_winners]
                        }
                    )

                # Send submission notification
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
        """Assign ranking points based on room capacity and position."""
        points_map = {
            2: {1: 50, 2: 0},
            5: {1: 70, 2: 40, 3: 0, 4: 0, 5: 0},
            10: {1: 100, 2: 60, 3: 40, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0}
        }
        return points_map.get(capacity, {1: 50}).get(position, 0)
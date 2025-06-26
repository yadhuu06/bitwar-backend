from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from problems.models import Question, TestCase, SolvedCode
from problems.serializers import QuestionListSerializer, TestCaseSerializer
from problems.utils import extract_function_name_and_params
from .models import BattleResult
from django.shortcuts import get_object_or_404
from django.utils import timezone
import logging
from problems.utils import wrap_user_code
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

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils import timezone
import logging
from problems.models import Question, TestCase
from problems.services.judge0_service import verify_with_judge0
from problems.utils import wrap_user_code  # Assuming this is your utility
logger = logging.getLogger(__name__)

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
            # Get the question
            question = Question.objects.filter(id=question_id).first()
            if not question:
                logger.error(f"Question not found: {question_id}")
                return Response({'error': 'Question not found'}, status=status.HTTP_404_NOT_FOUND)

            # Get test cases for the question
            testcases = TestCase.objects.filter(question=question)
            if not testcases:
                logger.error(f"No test cases found for question {question_id}")
                return Response({'error': 'No test cases available'}, status=status.HTTP_400_BAD_REQUEST)

            # ✅ Call verify_with_judge0 with raw code and testcases
            verification_result = verify_with_judge0(code, language, testcases)

            if 'error' in verification_result:
                logger.error(f"Judge0 verification failed: {verification_result['error']}")
                return Response(verification_result, status=status.HTTP_400_BAD_REQUEST)

            # ✅ Save result if all test cases passed
            if verification_result['all_passed']:
                battle_result, _ = BattleResult.objects.get_or_create(
                    room_id=room_id,
                    question=question,
                    defaults={'results': []}
                )
                position = len(battle_result.results) + 1
                battle_result.add_participant_result(
                    user=request.user,
                    position=position,
                    completion_time=timezone.now()
                )

            logger.info(f"Code verification {'successful' if verification_result['all_passed'] else 'failed'} for user {request.user.username} in room {room_id}")
            return Response(verification_result, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error verifying code for question {question_id}: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

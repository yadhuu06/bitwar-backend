# problems/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from problems.models import Question
from problems.serializers import QuestionListSerializer

import logging

logger = logging.getLogger(__name__)

class QuestionDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        try:
            question = Question.objects.get(id=id)
            serializer = QuestionListSerializer(question)
            logger.info(f"Fetched question {id}: {question.title}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Question.DoesNotExist:
            logger.error(f"Question not found: {id}")
            return Response({'error': 'Question not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error fetching question {id}: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
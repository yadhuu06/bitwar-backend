from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated  # Changed to allow authenticated users
from .models import Question
from .serializers import QuestionInitialCreateSerializer, QuestionListSerializer

class QuestionCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]  # Allow authenticated users, extend for contributions later

    def post(self, request):
        print("Create question data:", request.data)
        serializer = QuestionInitialCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            question = serializer.save()
            return Response({
                "message": "Question created successfully",
                "id": question.id,
                "slug": question.slug
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, question_id):
        print("Edit question data:", request.data)
        try:
            question = Question.objects.get(question_id=question_id)
        except Question.DoesNotExist:
            return Response({"error": "Question not found"}, status=status.HTTP_404_NOT_FOUND)

        # Check if the user is allowed to edit (admin or question creator)
        if not request.user.is_staff and question.created_by != request.user:
            return Response({"error": "You do not have permission to edit this question"}, status=status.HTTP_403_FORBIDDEN)

        serializer = QuestionInitialCreateSerializer(question, data=request.data, context={'request': request}, partial=True)
        if serializer.is_valid():
            question = serializer.save()
            return Response({
                "message": "Question updated successfully",
                "id": question.id,
                "slug": question.slug
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class QuestionsAPIView(APIView):
    permission_classes = [IsAuthenticated] 
    def get(self, request):
        questions = Question.objects.all()
        serializer = QuestionListSerializer(questions, many=True)
        return Response({"questions": serializer.data}, status=status.HTTP_200_OK)
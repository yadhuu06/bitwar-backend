from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import Question, TestCase
from .serializers import QuestionInitialCreateSerializer, QuestionListSerializer, TestCaseSerializer
from rest_framework.pagination import PageNumberPagination

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class QuestionCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

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

class QuestionDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, question_id):
        try:
            question = Question.objects.get(question_id=question_id)
        except Question.DoesNotExist:
            return Response({"error": "Question not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = QuestionListSerializer(question)
        return Response(serializer.data, status=status.HTTP_200_OK)

class QuestionsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        questions = Question.objects.all()
        serializer = QuestionListSerializer(questions, many=True)
        return Response({"questions": serializer.data}, status=status.HTTP_200_OK)

class TestCaseListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get(self, request, question_id):
        try:
            question = Question.objects.get(question_id=question_id)
        except Question.DoesNotExist:
            return Response({"error": "Question not found"}, status=status.HTTP_404_NOT_FOUND)

        test_cases = question.test_cases.all()
        search = request.query_params.get('search', '')
        is_sample = request.query_params.get('is_sample', None)
        if search:
            test_cases = test_cases.filter(input_data__icontains=search) | test_cases.filter(expected_output__icontains=search)
        if is_sample is not None:
            test_cases = test_cases.filter(is_sample=is_sample.lower() == 'true')
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(test_cases, request)
        serializer = TestCaseSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, question_id):
        try:
            question = Question.objects.get(question_id=question_id)
        except Question.DoesNotExist:
            return Response({"error": "Question not found"}, status=status.HTTP_404_NOT_FOUND)

        if not request.user.is_staff and question.created_by != request.user:
            return Response({"error": "You do not have permission to add test cases"}, status=status.HTTP_403_FORBIDDEN)

        serializer = TestCaseSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(question=question)
            return Response({
                "message": "Test case created successfully",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TestCaseRetrieveUpdateDestroyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, question_id, test_case_id):
        try:
            test_case = TestCase.objects.get(id=test_case_id, question__question_id=question_id)
        except TestCase.DoesNotExist:
            return Response({"error": "Test case not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = TestCaseSerializer(test_case)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, question_id, test_case_id):
        try:
            test_case = TestCase.objects.get(id=test_case_id, question__question_id=question_id)
        except TestCase.DoesNotExist:
            return Response({"error": "Test case not found"}, status=status.HTTP_404_NOT_FOUND)

        if not request.user.is_staff and test_case.question.created_by != request.user:
            return Response({"error": "You do not have permission to edit this test case"}, status=status.HTTP_403_FORBIDDEN)

        serializer = TestCaseSerializer(test_case, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Test case updated successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, question_id, test_case_id):
        try:
            test_case = TestCase.objects.get(id=test_case_id, question__question_id=question_id)
        except TestCase.DoesNotExist:
            return Response({"error": "Test case not found"}, status=status.HTTP_404_NOT_FOUND)

        if not request.user.is_staff and test_case.question.created_by != request.user:
            return Response({"error": "You do not have permission to delete this test case"}, status=status.HTTP_403_FORBIDDEN)

        test_case.delete()
        return Response({"message": "Test case deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
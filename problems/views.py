import re
import requests

from django.db import transaction
from django.shortcuts import render

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import CustomUser
from .models import Question, TestCase, SolvedCode
from .serializers import (
    QuestionInitialCreateSerializer,
    QuestionListSerializer,
    TestCaseSerializer,
    SolvedCodeSerializer
)
import ast
from . utils import extract_function_name,wrap_user_code,has_restricted_main_block

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class QuestionCreateAPIView(APIView):
    permission_classes = [IsAuthenticated,IsAdminUser]

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
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, question_id):
        try:
            question = Question.objects.get(question_id=question_id)
        except Question.DoesNotExist:
            return Response({"error": "Question not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = QuestionListSerializer(question)
        return Response(serializer.data, status=status.HTTP_200_OK)

class QuestionsAPIView(APIView):
    permission_classes = [IsAuthenticated,IsAdminUser]

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
    permission_classes = [IsAuthenticated ,IsAdminUser]

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
    


JUDGE0_URL = "http://localhost:2358/submissions?base64_encoded=false&wait=true"

LANGUAGE_MAP = {
    "python": 71,
    "cpp": 54,
    "java": 62,
    "javascript": 63,
}

class CodeVerifyAPIView(APIView):
    

    def post(self, request, question_id):
        print("data",request.data)
        code = request.data.get("code")
        language = request.data.get("language")

        if not code or not language:
            return Response({"error": "Code or language required"}, status=400)
        if language not in LANGUAGE_MAP:
            return Response({"error": "Unsupported language"}, status=400)
        
        try:
            question = Question.objects.get(question_id=question_id)
        except Question.DoesNotExist:
            return Response({"error": "Question not found"}, status=404)
        
        testcases = question.test_cases.all()
        if not testcases.exists():
            return Response({"error": "No test cases available for the question"}, status=404)
        
        if language == "python":
            if has_restricted_main_block(code):
                return Response({"error": "Do not include 'if __name__ == \"__main__\":' block in your submission"}, status=400)
        
        all_passed = True
        test_results = []

        for test in testcases:
            try:
                submission_code = wrap_user_code(code, language)
            except ValueError as e:
                return Response({"error": "Code processing failed", "details": str(e)}, status=400)
            
            payload = {
                "source_code": submission_code,
                "language_id": LANGUAGE_MAP[language],
                "stdin": test.input_data,
            }
            try:
                response = requests.post(JUDGE0_URL, json=payload, timeout=15)
                if response.status_code != 201:
                    return Response({"error": "Judge0 error", "details": response.text}, status=500)
                
                result = response.json()
                actual_output = (result.get("stdout") or "").strip()
                print("actual out",actual_output)
                expected_output = (test.expected_output or "").strip()
                print("expected",expected_output)
                error_output = (result.get("stderr") or result.get("compile_output") or "").strip()
                print("errorr",error_output)
                try:
                    actual_eval = ast.literal_eval(actual_output)
                    expected_eval = ast.literal_eval(expected_output)
                    passed = actual_eval == expected_eval
                except Exception:
                    passed = actual_output.strip() == expected_output.strip()

                if not passed:
                    all_passed = False
                
                test_results.append({
                    "test_case_id": test.id,
                    "input": test.input_data,
                    "expected": expected_output,
                    "actual": actual_output,
                    "error": error_output if error_output else None,
                    "passed": passed,
                })
            except requests.RequestException as e:
                return Response({"error": "Judge0 request failed", "details": str(e)}, status=500)
        
        solved_data = None
        if all_passed:
            with transaction.atomic():
                SolvedCode.objects.filter(question=question, language=language).delete()
                solved = SolvedCode.objects.create(
                    question=question,
                    language=language,
                    solution_code=code
                )
                if question.is_contributed and request.user.is_superuser==False:
                    question.is_validate = False
                else:
                    question.is_validate = True
                question.save()
                serializer = SolvedCodeSerializer(solved)
                solved_data = serializer.data

        return Response({
            "message": "Verification completed.",
            "all_passed": all_passed,
            "results": test_results,
            "solved_code": solved_data
        }, status=200)
    
    def get(self, request, question_id):
        try:
            question = Question.objects.get(question_id=question_id)
        except Question.DoesNotExist:
            return Response({"error": "Question not found"}, status=404)
        
        if request.path.endswith('solved-codes/'):
            try:
                solved_codes = SolvedCode.objects.filter(question=question)
                solved_data = {
                    code.language: SolvedCodeSerializer(code).data for code in solved_codes
                }
                return Response({"solved_codes": solved_data}, status=200)
            except Exception as e:
                return Response({"error": "Failed to fetch solved codes", "details": str(e)}, status=500)
        
        language = request.query_params.get("language")
        if not language:
            return Response({"error": "Language parameter required"}, status=400)
        if language not in LANGUAGE_MAP:
            return Response({"error": "Unsupported language"}, status=400)
        
        try:
            solved = SolvedCode.objects.filter(question=question, language=language).first()
            solved_data = SolvedCodeSerializer(solved).data if solved else None
            return Response({"solved_code": solved_data}, status=200)
        except Exception as e:
            return Response({"error": "Failed to fetch solved code", "details": str(e)}, status=500)
        

    def patch(self, request, question_id):
        try:
            question = Question.objects.get(question_id=question_id)
            print("my question is ", question)
        except Question.DoesNotExist:
            print("question not found")
            return Response({"error": "Question not found"}, status=status.HTTP_404_NOT_FOUND)
        
        if not question.is_validate:
            return Response({"error": "Please verify the question first"}, status=status.HTTP_400_BAD_REQUEST)
        
        new_status = request.data.get("status")
        if not new_status:
            return Response({"error": "No status provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        valid_statuses = [choice[0] for choice in Question.CONTRIBUTION_STATUS_CHOICES]
        if new_status not in valid_statuses:
            return Response({"error": f"Invalid status. Must be one of {valid_statuses}"}, status=status.HTTP_400_BAD_REQUEST)
        
        question.contribution_status = new_status
        question.save()
        return Response({"message": "Status updated"}, status=status.HTTP_200_OK)
        



        new_status = request.data.get("status")
        
        if new_status:
            question.contribution_status = new_status
            question.save()
            return Response({"message": "Status updated"}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "No status provided"}, status=status.HTTP_400_BAD_REQUEST)






class QuestionContributeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        user = request.user
        data = request.data.copy()
        data['created_by'] = user.user_id
        data['is_contributed'] = True

        question_serializer = QuestionInitialCreateSerializer(data=data, context={'request': request})
        if question_serializer.is_valid():
            question = question_serializer.save()
            question.contribution_status = 'QUESTION_SUBMITTED'
            question.is_contributed=True
            question.save()
            return Response(
                {"message": "Question created", "question_id": str(question.question_id)},
                status=status.HTTP_201_CREATED
            )
        return Response({'errors': question_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
class ContributeTestCasesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, question_id):
        print("data", request.data)
        print("questionID:", question_id)
        try:
            question = Question.objects.get(question_id=question_id, created_by=request.user, is_contributed=True)
            print("question", question)
        except Question.DoesNotExist:
            print("no question found")
            return Response({"error": "Question not found or not owned by user"}, status=status.HTTP_404_NOT_FOUND)

        if question.contribution_status != 'QUESTION_SUBMITTED':
            return Response({"error": "Question must be in 'QUESTION_SUBMITTED' status"}, status=status.HTTP_400_BAD_REQUEST)

        test_cases_data = request.data.get('test_cases', [])
        if not test_cases_data:
            return Response({"error": "At least one test case is required"}, status=status.HTTP_400_BAD_REQUEST)

        for idx, tc_data in enumerate(test_cases_data):
            tc_data['order'] = tc_data.get('order', idx + 1)
            serializer = TestCaseSerializer(data=tc_data)
            if not serializer.is_valid():
                return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            serializer.save(question=question)

        question.contribution_status = 'TEST_CASES_SUBMITTED'
        question.save()
        return Response(
            {"message": "Test cases submitted", "question_id": str(question.question_id)},
            status=status.HTTP_201_CREATED
        )

class UserContributionsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            problems_submitted = Question.objects.filter(created_by=user, is_contributed=True).count()
            solutions_accepted = SolvedCode.objects.filter(question__created_by=user, question__is_validate=True).count()
            recent_contributions = Question.objects.filter(created_by=user, is_contributed=True).order_by('-created_at')[:3]
            recent_data = [
                {
                    "title": q.title,
                    "date": q.created_at.strftime("%Y-%m-%d"),
                    "type": "Submitted Question",
                    "status":q.contribution_status
                } for q in recent_contributions
            ]
            return Response({
                "problems_submitted": problems_submitted,
                "solutions_accepted": solutions_accepted,
                "recent_contributions": recent_data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
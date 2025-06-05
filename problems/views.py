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
    

from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Question, TestCase, SolvedCode
import requests
import re

JUDGE0_URL = "http://localhost:2358/submissions?base64_encoded=false&wait=true"

LANGUAGE_MAP = {
    "python": 71,
    "cpp": 54,
    "java": 62,
    "javascript": 63,
}

class CodeVerifyAPIView(APIView):
    def post(self, request, question_id):
        code = request.data.get("code")
        language = request.data.get("language")

        if not code or not language:
            return Response({"error": "Code or language required"}, status=400)
        if language not in LANGUAGE_MAP:
            return Response({"error": "Unsupported language"}, status=400)
        
        try:
            question = Question.objects.get(question_id=question_id)
        except Question.DoesNotExist:
            return Response({"error": "Failed to find the question"}, status=404)
        
        testcases = question.test_cases.all()

        if not testcases.exists():
            return Response({"error": "No test cases available for the question"}, status=404)
        
        # Check for restricted main block in Python code
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
                print("Sending to Judge0:", payload)

                response = requests.post(JUDGE0_URL, json=payload, timeout=15)
                if response.status_code != 201:
                    return Response({"error": "Judge0 error", "details": response.text}, status=500)
                
                result = response.json()
                print("Received from Judge0:", result)

                actual_output = (result.get("stdout") or "").strip()
                expected_output = (test.expected_output or "").strip()
                error_output = (result.get("stderr") or result.get("compile_output") or "").strip()
                passed = actual_output == expected_output

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
                solved = SolvedCode.objects.create(
                    question=question,
                    language=language,
                    solution_code=code
                )
                question.is_validate = True  # Consider renaming to is_validated
                question.save()
                solved_data = {
                    "id": solved.id,
                    "language": solved.language,
                    "created_at": solved.created_at,
                }

        return Response({
            "message": "Verification completed.",
            "all_passed": all_passed,
            "results": test_results,
            "solved_code": solved_data
        }, status=200)

def extract_function_name(code: str) -> str:
    match = re.search(r'def\s+(\w+)\s*\(', code)  # For Python
    if match:
        return match.group(1)
    match = re.search(r'function\s+(\w+)\s*\(', code)  # For JavaScript
    if match:
        return match.group(1)
    raise ValueError("No function definition found in code")

def has_restricted_main_block(code: str) -> bool:
    pattern = r'if\s+__name__\s*==\s*[\'""]__main__[\'""]\s*:'
    return bool(re.search(pattern, code))

def wrap_user_code(code: str, language: str) -> str:
    if language == "python":
        fn = extract_function_name(code)
        return f"""import ast\n{code}\n\nif __name__ == "__main__":\n    arr = ast.literal_eval(input())\n    print({fn}(arr))"""

    elif language == "javascript":
        fn = extract_function_name(code)
        return f"""{code}\n\nconst readline = require('readline');\nconst rl = readline.createInterface({{\n  input: process.stdin,\n  output: process.stdout,\n}});\n\nrl.on('line', function(line) {{\n  const arr = JSON.parse(line);\n  console.log({fn}(arr));\n  rl.close();\n}});"""

    elif language == "go":
        fn = extract_function_name(code)
        return f"""package main\n\nimport (\n\t"encoding/json"\n\t"fmt"\n\t"os"\n)\n\n{code}\n\nfunc main() {{\n\tvar arr []int\n\terr := json.NewDecoder(os.Stdin).Decode(&arr)\n\tif err != nil {{\n\t\tfmt.Println("Error:", err)\n\t\treturn\n\t}}\n\tfmt.Println({fn}(arr))\n}}"""

    elif language in ["cpp", "java"]:
        return code  # Assume user provides complete code for C++ and Java
    else:
        raise ValueError("Unsupported language")
from django.shortcuts import render
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from .models import Question, TestCase, SolvedCode
from .serializers import (
    QuestionInitialCreateSerializer,
    QuestionListSerializer,
    TestCaseSerializer
)

import requests
import re


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
import requests
import re
from .models import Question, SolvedCode
from .serializers import SolvedCodeSerializer  # Added serializer import

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
                SolvedCode.objects.filter(question=question, language=language).delete()
                solved = SolvedCode.objects.create(
                    question=question,
                    language=language,
                    solution_code=code
                )
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

def extract_function_name(code: str) -> str:
    # Improved regex to handle more cases
    patterns = [
        r'def\s+(\w+)\s*\(',  # Python
        r'function\s+(\w+)\s*\(',  # JavaScript
        r'public\s+(?:static\s+)?(?:\w+\s+)?(\w+)\s*\(',  # Java
        r'(?:int|void|double|float|char|string)\s+(\w+)\s*\(',  # C++
    ]
    
    for pattern in patterns:
        match = re.search(pattern, code)
        if match:
            return match.group(1)
    
    raise ValueError("No valid function definition found in code")

def has_restricted_main_block(code: str) -> bool:
    pattern = r'if\s+__name__\s*==\s*[\'""]__main__[\'""]\s*:'
    return bool(re.search(pattern, code))

def wrap_user_code(code: str, language: str) -> str:
    try:
        fn = extract_function_name(code)
        if language == "python":
            return f"""import ast\n{code}\n\nif __name__ == "__main__":\n    arr = ast.literal_eval(input())\n    print({fn}(arr))"""
        elif language == "javascript":
            return f"""{code}\n\nconst readline = require('readline');\nconst rl = readline.createInterface({{\n  input: process.stdin,\n  output: process.stdout,\n}});\n\nrl.on('line', (line) => {{\n  const arr = JSON.parse(line);\n  console.log({fn}(arr));\n  rl.close();\n}});"""
        elif language == "java":
            # Ensure class name matches the main class
            class_name = re.search(r'class\s+(\w+)', code)
            if not class_name:
                raise ValueError("No class definition found in Java code")
            class_name = class_name.group(1)
            return f"""{code}\n\npublic class Main {{\n    public static void main(String[] args) throws Exception {{\n        java.util.Scanner sc = new java.util.Scanner(System.in);\n        String input = sc.nextLine();\n        {class_name} solution = new {class_name}();\n        System.out.println(solution.{fn}(input));\n        sc.close();\n    }}\n}}"""
        elif language == "cpp":
            return f"""#include <iostream>\n#include <string>\n{code}\n\nint main() {{\n    std::string input;\n    std::getline(std::cin, input);\n    std::cout << {fn}(input) << std::endl;\n    return 0;\n}}"""
        else:
            raise ValueError("Unsupported language")
    except Exception as e:
        raise ValueError(f"Failed to wrap code: {str(e)}")

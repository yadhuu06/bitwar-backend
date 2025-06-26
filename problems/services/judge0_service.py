import requests
import ast
import logging
from django.conf import settings
from problems.utils import wrap_user_code
from problems.serializers import TestCaseSerializer

logger = logging.getLogger(__name__)

LANGUAGE_MAP = {
    "python": 71,
    "cpp": 54,
    "java": 62,
    "javascript": 63,
}

def verify_with_judge0(code, language, testcases):
    if language not in LANGUAGE_MAP:
        logger.error(f"Unsupported language: {language}")
        return {"error": "Unsupported language"}

    all_passed = True
    results = []

    for test in testcases:
        logger.info(f"Processing test case {test.id}, input: {test.input_data}, expected: {test.expected_output}")
        try:
            parsed_input = ast.literal_eval(test.input_data)
            logger.info(f"Parsed input: {parsed_input}")
            if isinstance(parsed_input, dict):
                stdin = str(parsed_input)
            elif isinstance(parsed_input, (list, tuple)):
                stdin = str(parsed_input)
            else:
                stdin = str(parsed_input)
        except (ValueError, SyntaxError) as e:
            logger.error(f"Failed to parse input_data: {test.input_data}, error: {str(e)}")
            stdin = test.input_data

        try:
            wrapped_code = wrap_user_code(code, language, test.input_data)
            logger.info(f"Wrapped code: {wrapped_code}")
        except ValueError as e:
            logger.error(f"Failed to wrap code: {str(e)}")
            return {"error": f"Failed to wrap code: {str(e)}"}

        payload = {
            "source_code": wrapped_code,
            "language_id": LANGUAGE_MAP[language],
            "stdin": stdin,
        }
        logger.info(f"Judge0 payload: {payload}")

        try:
            response = requests.post(settings.JUDGE0_API_URL, json=payload, timeout=15)
            logger.info(f"Judge0 response: {response.json()}")
            if response.status_code != 201:
                logger.error(f"Judge0 request failed with status {response.status_code}: {response.text}")
                return {"error": "Judge0 error", "details": response.text, "status_code": response.status_code}

            result = response.json()
            actual_output = (result.get("stdout") or "").strip()
            expected_output = (test.expected_output or "").strip()
            error_output = (result.get("stderr") or result.get("compile_output") or "").strip()

            if not actual_output and expected_output:
                logger.error(f"No output produced, expected: {expected_output}")
                passed = False
            else:
                try:
                    actual_eval = ast.literal_eval(actual_output) if actual_output else None
                    expected_eval = ast.literal_eval(expected_output) if expected_output else None
                    passed = actual_eval == expected_eval
                except Exception:
                    passed = actual_output == expected_output

            if not passed:
                all_passed = False
                results.append({
                    "test_case_id": test.id,
                    "input": test.input_data,
                    "expected": expected_output,
                    "actual": actual_output,
                    "error": error_output if error_output else None,
                    "passed": passed,
                    "error_message": f"Test case failed: expected {expected_output}, got {actual_output}"
                })
            else:
                results.append({
                    "test_case_id": test.id,
                    "input": test.input_data,
                    "expected": expected_output,
                    "actual": actual_output,
                    "error": error_output if error_output else None,
                    "passed": passed,
                })
            logger.info(f"Test case {test.id} result: {results[-1]}")
        except requests.Timeout:
            logger.error("Judge0 request timed out")
            return {"error": "Judge0 request timed out"}
        except requests.RequestException as e:
            logger.error(f"Judge0 request failed: {str(e)}")
            return {"error": "Request failed", "details": str(e)}
        
    print("did all passed",all_passed)
    return {
        "all_passed": all_passed,
        "results": results,
    }
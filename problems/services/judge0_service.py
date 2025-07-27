import requests
import json
import logging
import ast
from django.conf import settings
from ..utils import validate_input_for_language, wrap_user_code

logger = logging.getLogger(__name__)

LANGUAGE_MAP = {
    "python": 71,
    "cpp": 54,
    "java": 62,
    "javascript": 63,
    "go": 95,
}

def verify_with_judge0(code, language, testcases):
    if language not in LANGUAGE_MAP:
        logger.error(f"Unsupported language: {language}")
        return {"error": "Unsupported language"}

    all_passed = True
    results = []

    for test in testcases:
        logger.info(f"Processing test case {test.id}, input: {test.input_data}, expected: {test.expected_output}")
        validation_result = validate_input_for_language(code, language, test.input_data)
        if not validation_result["valid"]:
            logger.error(f"Input validation failed: {validation_result['error']}")
            return {"error": validation_result["error"]}

        stdin = json.dumps(validation_result["args"]) if language in ["javascript", "go"] else repr(validation_result["args"])

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
            "cpu_time_limit": 2,
            "memory_limit": 128000,
        }
        logger.info(f"Judge0 payload: {payload}")

        try:
            response = requests.post(settings.JUDGE0_API_URL, json=payload, timeout=15)
            logger.info(f"Judge0 response: {response.json()}")
            if response.status_code != 201:
                logger.error(f"Judge0 request failed with status {response.status_code}: {response.text}")
                return {"error": "Judge0 error", "details": response.text, "status_code": response.status_code}

            result = response.json()
            actual_output = (result.get("stdout") or "").strip() or None
            expected_output = (test.expected_output or "").strip() or None
            error_output = (result.get("stderr") or result.get("compile_output") or "").strip()

            # Normalize outputs
            if expected_output is None and actual_output is None:
                passed = True
            else:
                try:
                    # Handle string outputs explicitly
                    if expected_output and not (expected_output.startswith(('"', '[', '{', '(')) or expected_output in ('True', 'False', 'None', 'null', 'true', 'false')):
                        expected_output_quoted = f'"{expected_output}"'
                    else:
                        expected_output_quoted = expected_output

                    # Parse outputs based on language
                    if language in ["javascript", "go"]:
                        actual_eval = json.loads(actual_output) if actual_output else None
                        expected_eval = json.loads(expected_output_quoted) if expected_output_quoted else None
                    else:
                        actual_eval = ast.literal_eval(actual_output) if actual_output else None
                        expected_eval = ast.literal_eval(expected_output_quoted) if expected_output_quoted else None
                    passed = actual_eval == expected_eval
                except (ValueError, SyntaxError, json.JSONDecodeError) as e:
                    logger.warning(f"Parsing failed, falling back to direct comparison: actual='{actual_output}', expected='{expected_output}', error: {str(e)}")
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
                    "error_message": f"Test case failed: expected '{expected_output}', got '{actual_output}'"
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

        except requests.Timeout:
            logger.error("Judge0 request timed out")
            return {"error": "Judge0 request timed out"}
        except requests.RequestException as e:
            logger.error(f"Judge0 request failed: {str(e)}")
            return {"error": "Request failed", "details": str(e)}

    return {"all_passed": all_passed, "results": results}
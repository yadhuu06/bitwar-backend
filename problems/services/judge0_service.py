import requests
import logging
import ast
from django.conf import settings
from ..utils import validate_input_for_language, wrap_user_code

logger = logging.getLogger(__name__)

LANGUAGE_MAP =settings.LANGUAGE_MAP

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

        stdin = validation_result["args"] if language in ["javascript", "go"] else str(validation_result["args"])

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
            if response.status_code != 201:
                logger.error(f"Judge0 request failed with status {response.status_code}: {response.text}")
                return {"error": "Judge0 error", "details": response.text, "status_code": response.status_code}

            result = response.json()
            logger.info(f"Judge0 response: {result}")

            actual_output = (result.get("stdout") or "").strip().rstrip("\r\n")
            logger.info(f"actual--------->>>>> {actual_output}")
            expected_output = str(test.expected_output).strip().rstrip("\r\n")
            
            if expected_output.startswith('"') and expected_output.endswith('"'):
                expected_output = expected_output[1:-1]
            logger.info(f"expected--------->>>>> {expected_output}")

            error_output = (result.get("stderr") or result.get("compile_output") or "").strip()

            
            try:
                actual_parsed = ast.literal_eval(actual_output)
                expected_parsed = ast.literal_eval(expected_output)
                passed = actual_parsed == expected_parsed
            except (ValueError, SyntaxError):
                
                passed = actual_output == expected_output

            results.append({
                "test_case_id": test.id,
                "input": test.input_data,
                "expected": expected_output,
                "actual": actual_output,
                "error": error_output if error_output else None,
                "passed": passed,
                "error_message": f"Test case failed: expected '{expected_output}', got '{actual_output}'" if not passed else None
            })

            if not passed:
                all_passed = False

        except requests.Timeout:
            logger.error("Judge0 request timed out")
            return {"error": "Judge0 request timed out"}
        except requests.RequestException as e:
            logger.error(f"Judge0 request failed: {str(e)}")
            return {"error": "Request failed", "details": str(e)}

    return {"all_passed": all_passed, "results": results}
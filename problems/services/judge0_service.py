import requests
import ast
from django.conf import settings

LANGUAGE_MAP = {
    "python": 71,
    "cpp": 54,
    "java": 62,
    "javascript": 63,
}

def verify_with_judge0(code, language, testcases):
    if language not in LANGUAGE_MAP:
        print("lang error-----------")
        return {"error": "Unsupported language"}

    all_passed = True
    results = []

    for test in testcases:
        print("test cases are", test)
        try:
            # Parse input_data to determine how to format it for Judge0
            parsed_input = ast.literal_eval(test.input_data)
            if isinstance(parsed_input, dict):
                stdin = str(parsed_input)  # JSON-like string for dict
            elif isinstance(parsed_input, (list, tuple)):
                stdin = str(parsed_input)  # List/tuple as string
            else:
                stdin = str(parsed_input)  # Single value or comma-separated values
        except (ValueError, SyntaxError):
            stdin = test.input_data  # Fallback to raw string if parsing fails

        payload = {
            "source_code": code,
            "language_id": LANGUAGE_MAP[language],
            "stdin": stdin,
        }
        try:
            response = requests.post(settings.JUDGE0_API_URL, json=payload, timeout=15)
            print("judge0 Response", response)
            if response.status_code != 201:
                return {"error": "Judge0 error", "details": response.text, "status_code": response.status_code}

            result = response.json()
            actual_output = (result.get("stdout") or "").strip()
            expected_output = (test.expected_output or "").strip()
            error_output = (result.get("stderr") or result.get("compile_output") or "").strip()

            try:
                actual_eval = ast.literal_eval(actual_output)
                expected_eval = ast.literal_eval(expected_output)
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
            })
        except requests.RequestException as e:
            return {"error": "Request failed", "details": str(e)}

    return {
        "all_passed": all_passed,
        "results": results,
    }
"""
PythonInputValidator

This module safely parses and validates input strings for a Python function.

Supported Input Formats:
-------------------------
1. **Keyword Argument Format (kwargs-style)**:
   Example: `x=1, y=[2, 3], z={"a": 10}`

2. **Positional Argument Format (tuple or list)**:
   Example: `[1, [2, 3], {"a": 10}]` or `(1, [2, 3], {"a": 10})`

Allowed Data Types:
-------------------
- int
- float
- bool
- str
- list, tuple (with nested values allowed)
- dict (only with string keys and allowed types as values)
- None

Disallowed: complex, set, custom objects, and any unsafe expressions.

Usage:
------
    validate_input(code_str, user_input_str)
        → returns a dict: { "valid": bool, "args": List[Any], "error": str }

Note:
-----
- This module uses Python's AST (Abstract Syntax Tree) for safe literal parsing.
- It checks if the user input matches the expected parameters of the function.
- Includes logging for debug and error tracking.

Author: Yadhu Krishnan PS
"""

import ast
import re
import logging
from typing import Any, Dict, List

# Setup logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()  # You can configure FileHandler if needed
formatter = logging.Formatter('%(levelname)s:%(name)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class PythonInputValidator:
    ALLOWED_TYPES = (int, float, bool, str, list, tuple, dict, type(None))

    def __init__(self, code: str):
        self.params = self._extract_parameters(code)
        logger.debug(f"Extracted function parameters: {self.params}")

    def _extract_parameters(self, code: str) -> List[str]:
        match = re.search(r'def\s+\w+\s*\((.*?)\)\s*:', code)
        if not match:
            logger.error("Function definition not found in code")
            raise ValueError("Function definition not found")
        param_str = match.group(1)
        return [param.strip().split('=')[0] for param in param_str.split(',') if param.strip()]

    def _safe_parse_assignment_str(self, input_str: str) -> Dict[str, Any]:
        try:
            tree = ast.parse(f"f({input_str})", mode='eval')
            if not isinstance(tree, ast.Expression) or not isinstance(tree.body, ast.Call):
                raise ValueError("Invalid format for keyword arguments")

            kwargs = {}
            for kw in tree.body.keywords:
                value = ast.literal_eval(kw.value)
                if not self._validate_type(value):
                    raise ValueError(f"Disallowed type: {type(value).__name__}")
                kwargs[kw.arg] = value
            logger.debug(f"Parsed keyword args: {kwargs}")
            return kwargs
        except Exception as e:
            logger.error(f"Keyword input parsing failed: {e}")
            raise ValueError(f"Invalid input: {str(e)}")

    def _safe_parse_positional(self, input_str: str) -> List[Any]:
        try:
            values = ast.literal_eval(input_str)
            if not isinstance(values, (tuple, list)):
                values = [values]
            for v in values:
                if not self._validate_type(v):
                    raise ValueError(f"Disallowed type: {type(v).__name__}")
            logger.debug(f"Parsed positional args: {values}")
            return values
        except Exception as e:
            logger.error(f"Positional input parsing failed: {e}")
            raise ValueError(f"Invalid input: {str(e)}")

    def _validate_type(self, value: Any) -> bool:
        if isinstance(value, self.ALLOWED_TYPES):
            if isinstance(value, dict):
                return all(isinstance(k, str) and self._validate_type(v) for k, v in value.items())
            if isinstance(value, (list, tuple)):
                return all(self._validate_type(v) for v in value)
            return True
        return False

    def validate(self, input_str: str) -> Dict[str, Any]:
        try:
            if '=' in input_str:
                parsed = self._safe_parse_assignment_str(input_str)
                if set(parsed.keys()) != set(self.params):
                    error_msg = f"Expected params {self.params}, got {list(parsed.keys())}"
                    logger.warning(error_msg)
                    return {
                        "valid": False,
                        "args": [],
                        "error": error_msg
                    }
                return {
                    "valid": True,
                    "args": [parsed[param] for param in self.params],
                    "error": ""
                }
            else:
                parsed = self._safe_parse_positional(input_str)
                if len(parsed) != len(self.params):
                    error_msg = f"Expected {len(self.params)} arguments, got {len(parsed)}"
                    logger.warning(error_msg)
                    return {
                        "valid": False,
                        "args": [],
                        "error": error_msg
                    }
                return {
                    "valid": True,
                    "args": parsed,
                    "error": ""
                }

        except ValueError as e:
            logger.error(f"Validation failed: {e}")
            return {"valid": False, "args": [], "error": str(e)}
        except Exception as e:
            logger.exception("Unexpected error during validation")
            return {"valid": False, "args": [], "error": f"Unexpected error: {str(e)}"}


def validate_input(code: str, input_str: str) -> Dict[str, Any]:
    validator = PythonInputValidator(code)
    return validator.validate(input_str)

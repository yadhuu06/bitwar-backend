
import logging
from django.conf import settings
from problems.serializers import TestCaseSerializer
from problems.validators import validate_python_input, validate_js_inputs, validate_go_input
from battle.utils import extract_function_name_and_params
import re

logger = logging.getLogger(__name__)



def validate_input_for_language(code: str, language: str, input_str: str):
    try:
        if language == "python":
            result = validate_python_input(code, input_str)
            return result
        elif language == "javascript":
            parsed = validate_js_inputs(input_str)
            if parsed is None:
                return {"valid": False, "args": [], "error": "Invalid JavaScript input"}
            return {"valid": True, "args": parsed, "error": ""}
        elif language == "go":
            valid, parsed = validate_go_input(input_str)
            if not valid:
                return {"valid": False, "args": [], "error": f"Invalid Go input: {parsed}"}
            return {"valid": True, "args": parsed, "error": ""}
        elif language in ["java", "cpp"]:
            try:
                parsed = TestCaseSerializer()._parse_input(input_str)
                return {"valid": True, "args": parsed, "error": ""}
            except Exception as e:
                return {"valid": False, "args": [], "error": str(e)}
        return {"valid": False, "args": [], "error": "Unsupported language"}
    except Exception as e:
        logger.error(f"Validation failed for {language}: {str(e)}")
        return {"valid": False, "args": [], "error": str(e)}

def extract_function_name(code: str) -> str:
    if "def " in code:
        try:
            result = extract_function_name_and_params(code, "python")
            return result["name"]
        except ValueError:
            pass
    patterns = [
        r'def\s+(\w+)\s*\(',  # Python
        r'function\s+(\w+)\s*\(',  # JavaScript
        r'public\s+(?:static\s+)?(?:\w+\s+)?(\w+)\s*\(',  # Java
        r'(?:int|void|double|float|char|string)\s+(\w+)\s*\(',  # C++
        r'func\s+(\w+)\s*\(',  # Go
    ]
    for pattern in patterns:
        match = re.search(pattern, code)
        if match:
            return match.group(1)
    raise ValueError("No valid function definition found in code")

def wrap_user_code(code: str, language: str, input_data: str) -> str:
    try:
        fn_info = extract_function_name_and_params(code, language) if language in ["python", "go"] else {"name": extract_function_name(code), "params": []}
        fn = fn_info["name"]
        logger.info(f"Function: {fn}, Parameters: {fn_info['params']}")

        validation_result = validate_input_for_language(code, language, input_data)
        if not validation_result["valid"]:
            raise ValueError(validation_result["error"])
        parsed_data = validation_result["args"]

        if language == "python":
            wrapper = f"""import ast\n{code}\n\nif __name__ == \"__main__\":\n"""
            wrapper += f"    input_str = input()\n"
            wrapper += f"    input_data = ast.literal_eval(input_str)\n"
            if isinstance(parsed_data, dict):
                wrapper += f"    result = {fn}(**input_data)\n"
            elif isinstance(parsed_data, (list, tuple)):
                wrapper += f"    result = {fn}(*input_data)\n"
            else:
                wrapper += f"    result = {fn}(input_data)\n"
            wrapper += f"    print(result)"

        elif language == "javascript":
            wrapper = f"""{code}\n\nconst readline = require('readline');\nconst rl = readline.createInterface({{\n  input: process.stdin,\n  output: process.stdout,\n}});\n\nrl.on('line', (line) => {{\n  const input_data = JSON.parse(line);\n  let result;\n"""
            if isinstance(parsed_data, dict):
                wrapper += f"  result = {fn}(input_data);\n"
            elif isinstance(parsed_data, (list, tuple)):
                wrapper += f"  result = {fn}(...input_data);\n"
            else:
                wrapper += f"  result = {fn}(input_data);\n"
            wrapper += f"  console.log(JSON.stringify(result));\n  rl.close();\n}});"

        elif language == "java":
            class_name = re.search(r'class\s+(\w+)', code)
            if not class_name:
                raise ValueError("No class definition found in Java code")
            class_name = class_name.group(1)
            wrapper = f"""{code}\n\npublic class Main {{\n    public static void main(String[] args) throws Exception {{\n        java.util.Scanner sc = new java.util.Scanner(System.in);\n        String input = sc.nextLine();\n        {class_name} solution = new {class_name}();\n"""
            if isinstance(parsed_data, (dict, list, tuple)):
                wrapper += f"        System.out.println(solution.{fn}(input));\n"
            else:
                wrapper += f"        System.out.println(solution.{fn}(input));\n"
            wrapper += f"        sc.close();\n    }}\n}}"

        elif language == "cpp":
            wrapper = f"""#include <iostream>\n#include <vector>\n#include <string>\n#include <sstream>\n{code}\n\nint main() {{\n    std::string input;\n    std::getline(std::cin, input);\n    std::stringstream ss(input);\n    std::vector<int> nums;\n    int num;\n    while (ss >> num) {{\n        nums.push_back(num);\n        if (ss.peek() == ',') ss.ignore();\n    }}\n"""
            wrapper += f"    std::cout << {fn}(nums) << std::endl;\n"
            wrapper += f"    return 0;\n}}"

        elif language == "go":
            wrapper = f"""package main\n\n{code}\n\nfunc main() {{\n    var input string\n    fmt.Scanln(&input)\n    var input_data interface{{}}\n    json.Unmarshal([]byte(input), &input_data)\n"""
            if isinstance(parsed_data, dict):
                wrapper += f"    result := {fn}(input_data.(map[string]interface{{}}))\n"
            elif isinstance(parsed_data, (list, tuple)):
                wrapper += f"    result := {fn}(input_data.([]interface{{}})...)\n"
            else:
                wrapper += f"    result := {fn}(input_data)\n"
            wrapper += f"    output, _ := json.Marshal(result)\n    fmt.Println(string(output))\n}}"
            wrapper = f"""package main\nimport "encoding/json"\nimport "fmt"\n{wrapper}"""

        else:
            raise ValueError("Unsupported language")

        logger.info(f"Generated wrapper code: {wrapper}")
        return wrapper
    except Exception as e:
        logger.error(f"Failed to wrap code: {str(e)}")
        raise ValueError(f"Failed to wrap code: {str(e)}")


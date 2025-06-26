import re
import ast
from .serializers import TestCaseSerializer
import logging

logger = logging.getLogger(__name__)

def extract_function_name(code: str) -> str:
    """Extract the function name from the provided code."""
    if "def " in code:  # Prioritize Python function extraction
        try:
            result = extract_function_name_and_params(code, "python")
            return result["name"]
        except ValueError:
            pass
    patterns = [
        r'def\s+(\w+)\s*\(',  # Python
        r'function\s+(\w+)\s*\(',  # JavaScript
        r'public\s+(?:static\s+)?(?:\w+\s+)?(\w+)\s*\(',  # Java
        r'(?:int|void|double|float|char|string)\s+(\w+)\s*\(',  # C++ and others
    ]
    for pattern in patterns:
        match = re.search(pattern, code)
        if match:
            return match.group(1)
    raise ValueError("No valid function definition found in code")

def extract_function_name_and_params(code: str, language: str) -> dict:
    """Extract function name and parameters from Python code."""
    if language != "python":
        raise ValueError("Only Python is supported for function extraction")

    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                params = [arg.arg for arg in node.args.args]
                return {"name": node.name, "params": params}
    except SyntaxError:
        pattern = r'def\s+(\w+)\s*\((.*?)\)\s*:'
        match = re.search(pattern, code)
        if match:
            name = match.group(1)
            params = [param.strip() for param in match.group(2).split(',') if param.strip()]
            return {"name": name, "params": params}
    raise ValueError("No valid function definition found in code")

def has_restricted_main_block(code: str) -> bool:
    """Check if Python code contains a restricted __main__ block."""
    pattern = r'if\s+__name__\s*==\s*[\'""]__main__[\'""]\s*:'
    return bool(re.search(pattern, code))

def wrap_user_code(code: str, language: str, input_data: str) -> str:
    """Wrap user code for Judge0 execution with dynamic argument handling."""
    try:
        fn_info = extract_function_name_and_params(code, language) if language == "python" else {"name": extract_function_name(code), "params": []}
        fn = fn_info["name"]
        params = fn_info["params"]
        logger.info(f"Function: {fn}, Parameters: {params}")
        if language == "python" and len(params) != 2:
            raise ValueError(f"Function {fn} must have exactly 2 parameters, got {len(params)}")
        if language == "python":
            parsed_data = TestCaseSerializer()._parse_input(input_data)
            logger.info(f"Parsed input data: {parsed_data}")
            wrapper = f"""import ast\n{code}\n\nif __name__ == "__main__":\n"""
            wrapper += f"    input_str = input()\n"
            wrapper += f"    input_data = ast.literal_eval(input_str)\n"
            if isinstance(parsed_data, dict):
                wrapper += f"    result = {fn}(**input_data)\n"
            elif isinstance(parsed_data, tuple) and len(parsed_data) == 2:
                wrapper += f"    a, b = input_data\n    result = {fn}(a, b)\n"
            elif isinstance(parsed_data, (list, tuple)):
                wrapper += f"    result = {fn}(*input_data)\n"
            else:
                wrapper += f"    result = {fn}(input_data)\n"
            wrapper += f"    print(result)"
        elif language == "javascript":
            wrapper = f"""{code}\n\nconst readline = require('readline');\nconst rl = readline.createInterface({{\n  input: process.stdin,\n  output: process.stdout,\n}});\n\nrl.on('line', (line) => {{\n  const input_data = JSON.parse(line);\n  let result;\n"""
            if isinstance(TestCaseSerializer()._parse_input(input_data), (dict, list, tuple)):
                wrapper += f"  result = {fn}(input_data);\n"
            else:
                wrapper += f"  result = {fn}(...input_data);\n"
            wrapper += f"  console.log(result);\n  rl.close();\n}});\n"
        elif language == "java":
            class_name = re.search(r'class\s+(\w+)', code)
            if not class_name:
                raise ValueError("No class definition found in Java code")
            class_name = class_name.group(1)
            wrapper = f"""{code}\n\npublic class Main {{\n    public static void main(String[] args) throws Exception {{\n        java.util.Scanner sc = new java.util.Scanner(System.in);\n        String input = sc.nextLine();\n        {class_name} solution = new {class_name}();\n"""
            if isinstance(TestCaseSerializer()._parse_input(input_data), (dict, list, tuple)):
                wrapper += f"        System.out.println(solution.{fn}(input));\n"
            else:
                wrapper += f"        java.util.List<Integer> list = java.util.Arrays.asList(input.split(\",\")).stream().map(Integer::parseInt).collect(java.util.stream.Collectors.toList());\n        System.out.println(solution.{fn}(list));\n"
            wrapper += f"        sc.close();\n    }}\n}}"
        elif language == "cpp":
            wrapper = f"""#include <iostream>\n#include <vector>\n#include <string>\n#include <sstream>\n{code}\n\nint main() {{\n    std::string input;\n    std::getline(std::cin, input);\n    std::stringstream ss(input);\n    std::vector<int> nums;\n    int num;\n    while (ss >> num) {{\n        nums.push_back(num);\n        if (ss.peek() == ',') ss.ignore();\n    }}\n"""
            wrapper += f"    std::cout << {fn}(nums) << std::endl;\n"
            wrapper += f"    return 0;\n}}"
        else:
            raise ValueError("Unsupported language")
        logger.info(f"Generated wrapper code: {wrapper}")
        return wrapper
    except Exception as e:
        logger.error(f"Failed to wrap code: {str(e)}")
        raise ValueError(f"Failed to wrap code: {str(e)}")
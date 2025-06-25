import re
import ast
from .serializers import TestCaseSerializer
def extract_function_name(code: str) -> str:

    patterns = [
        r'def\s+(\w+)\s*\(',  
        r'function\s+(\w+)\s*\(',  
        r'public\s+(?:static\s+)?(?:\w+\s+)?(\w+)\s*\(',  
        r'(?:int|void|double|float|char|string)\s+(\w+)\s*\(',  
    ]
    for pattern in patterns:
        match = re.search(pattern, code)
        if match:
            return match.group(1)
    raise ValueError("No valid function definition found in code")

def has_restricted_main_block(code: str) -> bool:

    pattern = r'if\s+__name__\s*==\s*[\'""]__main__[\'""]\s*:'
    return bool(re.search(pattern, code))

def wrap_user_code(code: str, language: str, input_data: str) -> str:
    try:
        fn = extract_function_name(code)
        if language == "python":

            parsed_data = TestCaseSerializer()._parse_input(input_data)
            wrapper = f"""import ast\n{code}\n\nif __name__ == "__main__":\n"""
            if isinstance(parsed_data, dict):
                wrapper += f"    result = {fn}(**{str(parsed_data)})\n"
            elif isinstance(parsed_data, tuple) and len(parsed_data) == 2 and isinstance(parsed_data[1], (int, float)):
                wrapper += f"    arr, addend = {str(parsed_data[0])}, {str(parsed_data[1])}\n    result = {fn}(arr, addend)\n"
            elif isinstance(parsed_data, (list, tuple)):
                wrapper += f"    result = {fn}(*{str(parsed_data)})\n"
            else:
                wrapper += f"    result = {fn}({str(parsed_data)})\n"
            wrapper += "    print(result)"
            return wrapper
        elif language == "javascript":
            return f"""{code}\n\nconst readline = require('readline');\nconst rl = readline.createInterface({{\n  input: process.stdin,\n  output: process.stdout,\n}});\n\nrl.on('line', (line) => {{\n  const input_data = JSON.parse(line);\n  const result = Array.isArray(input_data) ? {fn}(...input_data) : typeof input_data === 'object' ? {fn}(input_data) : {fn}(input_data);\n  console.log(result);\n  rl.close();\n}});"""
        elif language == "java":
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
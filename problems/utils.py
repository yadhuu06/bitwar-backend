# your_app/utils.py
import re

def extract_function_name(code: str) -> str:
    """Extract the function name from the provided code."""
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

def has_restricted_main_block(code: str) -> bool:
    """Check if Python code contains a restricted __main__ block."""
    pattern = r'if\s+__name__\s*==\s*[\'""]__main__[\'""]\s*:'
    return bool(re.search(pattern, code))

def wrap_user_code(code: str, language: str) -> str:
    """Wrap user code for Judge0 execution based on the language."""
    try:
        fn = extract_function_name(code)
        if language == "python":
            return f"""import ast\n{code}\n\nif __name__ == "__main__":\n    arr = ast.literal_eval(input())\n    print({fn}(arr))"""
        elif language == "javascript":
            return f"""{code}\n\nconst readline = require('readline');\nconst rl = readline.createInterface({{\n  input: process.stdin,\n  output: process.stdout,\n}});\n\nrl.on('line', (line) => {{\n  const arr = JSON.parse(line);\n  console.log({fn}(arr));\n  rl.close();\n}});"""
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
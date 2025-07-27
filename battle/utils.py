
import ast
import re

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


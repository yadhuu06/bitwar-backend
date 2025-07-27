import re
import json

def normalize_go_input(input_str):
    # Basic replacements
    input_str = input_str.strip()
    input_str = input_str.replace("nil", "null")
    input_str = re.sub(r"\btrue\b", "true", input_str)
    input_str = re.sub(r"\bfalse\b", "false", input_str)

    # Convert Go slice/array/map to JSON-like
    input_str = re.sub(r'\[\w*\]*\s*{', '[', input_str)  # []int{1,2} → [1,2]
    input_str = re.sub(r'map\[\w+\]\w+\s*{', '{', input_str)  # map[string]int{...} → { ... }

    # Ensure keys are quoted in map
    input_str = re.sub(r'([{,]\s*)([a-zA-Z_]\w*)(\s*:)', r'\1"\2"\3', input_str)

    # Convert single to double quotes
    input_str = re.sub(r"'", '"', input_str)

    return input_str

def validate_go_input(go_input: str):
    try:
        normalized = normalize_go_input(go_input)
        
        # If it's a comma-separated list without a surrounding structure, wrap in []
        if not (normalized.startswith("{") or normalized.startswith("[") or normalized.startswith('"')):
            normalized = "[" + normalized + "]"
        
        parsed = json.loads(normalized)
        return True, parsed
    except Exception as e:
        return False, str(e)

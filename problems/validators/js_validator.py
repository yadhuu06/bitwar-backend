import json
import re

def validate_js_inputs(input_string):
    try:
        input_string = input_string.strip()

        # Replace JS literals with temporary placeholders
        js_literals = {
            r'\btrue\b': '"__true__"',
            r'\bfalse\b': '"__false__"',
            r'\bnull\b': '"__null__"'
        }
        for pattern, replacement in js_literals.items():
            input_string = re.sub(pattern, replacement, input_string)

        # If multiple top-level values separated by commas, wrap in brackets
        if not (input_string.startswith('[') or input_string.startswith('{')):
            if "," in input_string and not input_string.startswith('"'):
                input_string = f"[{input_string}]"
            else:
                input_string = f"[{input_string}]"

        # Parse as JSON
        parsed = json.loads(input_string)

        def restore_literals(value):
            if isinstance(value, str):
                if value == "__true__":
                    return True
                elif value == "__false__":
                    return False
                elif value == "__null__":
                    return None
                return value
            elif isinstance(value, list):
                return [restore_literals(v) for v in value]
            elif isinstance(value, dict):
                return {k: restore_literals(v) for k, v in value.items()}
            return value

        return restore_literals(parsed)

    except Exception as e:
        print("Input parsing error:", str(e))
        return None

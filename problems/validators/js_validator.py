import ast
import re
import json

def validate_js_inputs(input_string):
    try:
        # Step 1: Trim any leading/trailing whitespace
        input_string = input_string.strip()

        # Step 2: Define JS literals and their placeholders
        js_literals = {
            r'\btrue\b': '"__true__"',   # Temporarily replace JS true with string
            r'\bfalse\b': '"__false__"', # Temporarily replace JS false with string
            r'\bnull\b': '"__null__"'    # Temporarily replace JS null with string
        }

        # Step 3: Replace JS-specific literals with temporary strings
        for pattern, replacement in js_literals.items():
            input_string = re.sub(pattern, replacement, input_string)

        # Step 4: Wrap in brackets if it's not a JSON array or object
        if not input_string.startswith(('[', '{')):
            input_string = f'[{input_string}]'

        # Step 5: Convert to Python object using json.loads
        parsed = json.loads(input_string)

        # Step 6: Recursive function to restore original JS literals
        def restore_literals(value):
            if isinstance(value, str):
                if value == "__true__":
                    return True     # Return as Python boolean True
                elif value == "__false__":
                    return False    # Return as Python boolean False
                elif value == "__null__":
                    return None     # Return as Python None (null)
                return value
            elif isinstance(value, list):
                return [restore_literals(item) for item in value]
            elif isinstance(value, dict):
                return {key: restore_literals(val) for key, val in value.items()}
            return value

        # Step 7: Return restored and validated object
        return restore_literals(parsed)

    except Exception as e:
        print("Input parsing error:", str(e))
        return None

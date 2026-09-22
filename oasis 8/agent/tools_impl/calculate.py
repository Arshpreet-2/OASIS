"""Tool: exact arithmetic. READ-ONLY.

Restricted to numbers and operators by a regular expression, so the model cannot
run arbitrary code through this path. Language models are unreliable at mental
arithmetic; this makes the sum exact and shows the working.
"""

import re


def tool_calculate(expression: str, **_ignored):
    """Evaluate arithmetic. Deliberately restricted to numbers and operators."""
    if not re.fullmatch(r"[0-9\.\+\-\*/\(\)\s]+", expression or ""):
        return {"error": "Only arithmetic is permitted here."}
    try:
        value = eval(expression, {"__builtins__": {}}, {})
    except Exception as e:
        return {"error": str(e)}
    return {"expression": expression, "result": value}

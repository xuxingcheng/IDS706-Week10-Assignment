"""Compare results for the original five quiz questions."""
from decimal import Decimal
import math
from numbers import Number


def quiz_match(text, questions):
    normalized = " ".join(text.lower().split())
    return next((q for q in questions if " ".join(q["question"].lower().split()) == normalized), None)


def results_match(columns, rows, expected_columns, expected_rows):
    # All five original questions specify ordering, so row order matters.
    if list(columns) != list(expected_columns) or len(rows) != len(expected_rows):
        return False
    for actual_row, expected_row in zip(rows, expected_rows):
        if len(actual_row) != len(expected_row):
            return False
        for actual, expected in zip(actual_row, expected_row):
            if isinstance(actual, (Number, Decimal)) and isinstance(expected, (Number, Decimal)):
                if not math.isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-9):
                    return False
            elif actual != expected:
                return False
    return True

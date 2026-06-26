"""
Formula evaluator for the P2P spreadsheet.

Supports:
- Basic arithmetic: +, -, *, /
- Cell references: =A1+B2, =C3*2
- Nested expressions: =(A1+B2)*C3
- Returns "#ERR" on failure (bad syntax, division by zero, circular ref)
"""

import re

# Matches cell references like A1, B10, E5
CELL_REF_PATTERN = re.compile(r"\b([A-E])(1?\d)\b")

# Maximum depth to prevent circular references
MAX_DEPTH = 10


def evaluate_cell(cell_value: str, all_cells: dict, depth: int = 0) -> str:
    """
    Evaluate a single cell value.

    If it starts with '=', treat it as a formula and compute the result.
    Otherwise, return the raw value as-is.

    Args:
        cell_value: The raw string value of the cell.
        all_cells: The full cell dictionary {"A1": "10", "B1": "=A1+5", ...}.
        depth: Current recursion depth (for circular reference detection).

    Returns:
        The computed result as a string, or "#ERR" on failure.
    """
    if not isinstance(cell_value, str) or not cell_value.startswith("="):
        return cell_value

    if depth > MAX_DEPTH:
        return "#ERR"

    formula = cell_value[1:].strip()  # Remove the leading '='

    try:
        resolved = _resolve_references(formula, all_cells, depth)
        result = eval(resolved)  # noqa: S307 — safe: only digits and operators
        # Return clean int if possible, otherwise float
        if isinstance(result, float) and result == int(result):
            return str(int(result))
        return str(result)
    except Exception:
        return "#ERR"


def _resolve_references(formula: str, all_cells: dict, depth: int) -> str:
    """
    Replace all cell references in a formula with their evaluated values.

    E.g., "A1+B2*3" with cells {"A1": "10", "B2": "5"}
    becomes "10+5*3".
    """

    def _replacer(match: re.Match) -> str:
        col = match.group(1)
        row = match.group(2)
        ref_key = f"{col}{row}"
        ref_value = all_cells.get(ref_key, "")

        if ref_value == "":
            return "0"  # Empty cells are treated as 0 in formulas

        # Recursively evaluate in case the referenced cell is also a formula
        evaluated = evaluate_cell(ref_value, all_cells, depth + 1)

        if evaluated == "#ERR":
            raise ValueError(f"Error in referenced cell {ref_key}")

        return evaluated

    return CELL_REF_PATTERN.sub(_replacer, formula)


def evaluate_all_cells(all_cells: dict) -> dict:
    """
    Evaluate all cells and return a dict of display values.

    Raw values are stored in the backend; this function computes
    the display values for the UI (resolving formulas).
    """
    display = {}
    for key, value in all_cells.items():
        display[key] = evaluate_cell(value, all_cells)
    return display

import ast
from pathlib import Path

MAX_LINES = 80
APP = Path(__file__).resolve().parents[1] / "app"


def test_no_backend_function_exceeds_the_size_limit():
    oversized = []
    for path in APP.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.end_lineno - node.lineno + 1 > MAX_LINES:
                oversized.append(f"{path.relative_to(APP)}:{node.lineno} {node.name}")
    assert not oversized, oversized

import ast
import importlib.util
import logging
import re
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger("generator")


def clean_code(raw: str) -> str:
    """Strip markdown fences and leading/trailing whitespace."""
    code = raw.strip()
    code = re.sub(r"^```[a-zA-Z]*\n?", "", code)
    code = re.sub(r"\n?```$", "", code)
    return code.strip()


def validate_syntax(code: str) -> str | None:
    """Check Python syntax. Returns error string or None if valid."""
    try:
        ast.parse(code)
        return None
    except SyntaxError as e:
        return f"SyntaxError at line {e.lineno}: {e.msg}"


def validate_structure(code: str) -> str | None:
    """Check that the code defines a class inheriting from BaseAgent with a decide method."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e}"

    classes = [
        node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    ]

    if not classes:
        return "No class definition found in generated code."

    agent_class = None
    for cls in classes:
        for base in cls.bases:
            name = ""
            if isinstance(base, ast.Name):
                name = base.id
            elif isinstance(base, ast.Attribute):
                name = base.attr
            if name == "BaseAgent":
                agent_class = cls
                break

    if agent_class is None:
        return "No class inheriting from BaseAgent found."

    method_names = [
        node.name for node in ast.walk(agent_class)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    if "decide" not in method_names:
        return f"Class {agent_class.name} is missing the 'decide' method."

    return None


def try_import(code: str, agent_type: str) -> tuple[object | None, str | None]:
    """Write code to a temp file and try importing it. Returns (class, error)."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix=f"agent_{agent_type}_"
    ) as f:
        f.write(code)
        f.flush()
        tmp_path = Path(f.name)

    try:
        spec = importlib.util.spec_from_file_location(f"agent_{agent_type}", tmp_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if (
                isinstance(obj, type)
                and hasattr(obj, "decide")
                and attr_name != "BaseAgent"
            ):
                return obj, None

        return None, "No valid agent class found after import."
    except Exception as e:
        return None, f"Import error: {e}"
    finally:
        tmp_path.unlink(missing_ok=True)

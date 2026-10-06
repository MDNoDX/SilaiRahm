"""Two mistakes the test suite can miss: unused imports and undefined names.

    python tools/check_code.py      # prints problems, exit code 1 if any

Undefined names are found with the compiler's own symbol tables: a name a
function reads as a global must be defined at module level or be a builtin.
"""
import ast
import builtins
import symtable
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {"migrations"}
BUILTINS = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__spec__", "__builtins__"}


def unused_imports(path, tree):
    if path.name == "__init__.py":
        return []
    imported = {}
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                imported[(alias.asname or alias.name).split(".")[0]] = node.lineno
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    exported = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            exported |= {e.value for e in node.value.elts}
    return [f"{path.relative_to(ROOT)}:{line}: '{name}' imported but unused"
            for name, line in imported.items() if name not in used | exported and name != "*"]


def undefined_names(path, source):
    top = symtable.symtable(source, str(path), "exec")
    defined = {s.get_name() for s in top.get_symbols() if s.is_assigned() or s.is_imported() or s.is_namespace()}
    out = []

    def visit(table):
        for sym in table.get_symbols():
            name = sym.get_name()
            if sym.is_referenced() and sym.is_global() and name not in defined and name not in BUILTINS:
                out.append(f"{path.relative_to(ROOT)}: '{name}' is used in {table.get_name()}() but never defined")
        for child in table.get_children():
            visit(child)

    for child in top.get_children():
        visit(child)
    return out


def run():
    found = []
    for base in ("apps", "config", "tests", "tools"):
        for path in sorted((ROOT / base).rglob("*.py")):
            if SKIP & set(path.parts):
                continue
            source = path.read_text(encoding="utf-8")
            found += unused_imports(path, ast.parse(source)) + undefined_names(path, source)
    return found


if __name__ == "__main__":
    found = run()
    print("\n".join(found) if found else "Code check passed.")
    sys.exit(1 if found else 0)

"""AGENTS.md is what makes goose reliable: the rules it states must be present, and the code in the repo must obey them.

The live check is `bestiary gate --only goose --runs 20` (needs goose and a model); these tests are the offline part.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS = (ROOT / "upstream" / "farolito" / "AGENTS.md").read_text(encoding="utf-8")
CLI_FILES = {"template (with the bug)": ROOT / "upstream" / "farolito" / "farolito" / "cli.py",
             "reference fix": ROOT / "upstream" / "reference_fix" / "cli.py"}


def test_agents_md_states_the_rules_that_goose_needs():
    for must in ("main()` returns the process exit code", "never call `sys.exit()`", "exit with code 2", "Run it before you say you are done",
                 "farolito: config file not found: <path>"):
        assert must in AGENTS, must


def _sys_exit_calls_inside_functions(tree: ast.AST) -> list[int]:
    lines = []
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for node in ast.walk(fn):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "exit"
                        and isinstance(node.func.value, ast.Name) and node.func.value.id == "sys"):
                    lines.append(node.lineno)
    return lines


def test_the_repo_code_obeys_its_own_agents_md():
    for label, path in CLI_FILES.items():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert _sys_exit_calls_inside_functions(tree) == [], f"{label}: a function calls sys.exit()"
        main = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "main")
        assert any(isinstance(n, ast.Return) for n in ast.walk(main)), f"{label}: main() must return the exit code"


def test_the_rule_catches_the_wrong_fix_goose_wrote_on_the_first_recording():
    wrong = '''
import sys
def load_config(path):
    try:
        open(path)
    except FileNotFoundError:
        print("farolito: config file not found", file=sys.stderr)
        sys.exit(2)
'''
    assert _sys_exit_calls_inside_functions(ast.parse(wrong)) != []

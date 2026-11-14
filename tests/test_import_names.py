import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def scope_imports(function):
    """(name, where from, branches) for each import in `function`'s own scope, not in
    functions or classes inside it. branches: the (if statement, 'body' or 'orelse') it is in."""
    found = []

    def visit(node, branches):
        if isinstance(node, SCOPES):
            return
        if isinstance(node, ast.ImportFrom):
            found.extend((a.asname or a.name, f'{node.module}.{a.name}', branches) for a in node.names)
        elif isinstance(node, ast.Import):
            found.extend((a.asname or a.name.split('.')[0], a.name, branches) for a in node.names)
        elif isinstance(node, ast.If):
            visit(node.test, branches)
            for part in ('body', 'orelse'):
                for child in getattr(node, part):
                    visit(child, branches + ((id(node), part),))
            return
        for child in ast.iter_child_nodes(node):
            visit(child, branches)

    for statement in function.body:
        visit(statement, ())
    return found


def exclusive(first, second):
    """Whether two imports sit in different branches of one if statement (only one runs)."""
    inside = dict(first)
    return any(node in inside and inside[node] != part for node, part in second)


def clashes(source):
    """Names that one function imports from two places: the later import replaces the
    earlier one for the whole function (seen 2026-11-14: the pedals' `combined` replaced the
    flags' on Linux, and every HUD frame failed). Imports in an if's other branch are fine."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            imports = scope_imports(node)
            names = {
                name
                for i, (name, origin, branches) in enumerate(imports)
                for other, other_origin, other_branches in imports[i + 1 :]
                if other == name and other_origin != origin and not exclusive(branches, other_branches)
            }
            found += [(node.name, name) for name in sorted(names)]
    return found


class ImportNameTests(unittest.TestCase):
    def test_the_check_finds_a_clash(self):
        source = (
            'def run():\n'
            '    from a import combined\n'
            '    if x:\n'
            '        from b import combined\n'
            '    def inner():\n'
            '        from c import combined\n'
        )
        self.assertEqual(clashes(source), [('run', 'combined')])

    def test_one_import_per_branch_is_no_clash(self):
        source = (
            'def native():\n'
            '    if a:\n'
            '        from x import Native\n'
            '    elif b:\n'
            '        from y import Native\n'
            '    else:\n'
            '        from z import Native\n'
        )
        self.assertEqual(clashes(source), [])

    def test_the_same_import_twice_is_no_clash(self):
        self.assertEqual(clashes('def run():\n    from a import b\n    if x:\n        from a import b\n'), [])

    def test_no_function_in_turbohud_imports_one_name_from_two_places(self):
        for path in sorted((ROOT / 'turbohud').rglob('*.py')):
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertEqual(clashes(path.read_text(encoding='utf-8')), [])


if __name__ == '__main__':
    unittest.main()

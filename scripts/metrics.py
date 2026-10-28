"""Measure all Python callables and module maintainability."""

from __future__ import annotations

import ast

from radon.metrics import mi_visit
from radon.visitors import ComplexityVisitor


class Callables(ast.NodeVisitor):
    def __init__(self) -> None:
        self.path: list[str] = []
        self.results: list[tuple[int, str, int]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.path.append(node.name)
        self.generic_visit(node)
        self.path.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.path.append(node.name)
        functions = ComplexityVisitor.from_ast(node).functions
        if len(functions) != 1:
            raise ValueError(f"missing complexity result for {node.name}:{node.lineno}")
        self.results.append((node.lineno, ".".join(self.path), functions[0].complexity))
        self.generic_visit(node)
        self.path.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node: ast.Lambda) -> None:
        visitor = ComplexityVisitor.from_ast(node.body)
        self.results.append((node.lineno, ".".join([*self.path, "<lambda>"]), visitor.complexity))
        self.generic_visit(node)


def measure(source: str) -> tuple[float, list[tuple[int, str, int]]]:
    tree = ast.parse(source)
    visitor = Callables()
    visitor.visit(tree)
    return mi_visit(source, multi=False), visitor.results

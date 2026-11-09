"""Safe expression parser for indicator numerator/denominator filters.

A logframe author writes short boolean expressions in ``logframe.yml`` like:

    sex == 'female' and age >= 18
    selected(services_used, 'health')
    isna(phone)

We refuse to use :func:`eval` because logframe files may be checked in and
edited by multiple people. Instead we parse the expression with :mod:`ast`,
reject anything that isn't on an allowlist of node types, and then evaluate
by walking the tree ourselves against a dict of column values.

The intentional subset supported:

- Literal ``int`` / ``float`` / ``str`` / ``True`` / ``False`` / ``None``
- Column names and attribute-free identifiers (one word)
- Comparisons: ``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``
- Boolean operators: ``and``, ``or``, ``not``
- Membership: ``in`` / ``not in`` with a list literal on the right
- Function calls limited to ``selected(col, 'value')``, ``isna(col)``,
  ``between(col, low, high)``, ``in_list(col, ['a', 'b'])`` and
  ``startswith(col, 'prefix')``

Anything else raises :class:`IndicatorError` with the offending node.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from typing import Any

from zyuka.errors import IndicatorError

ALLOWED_FUNCS: dict[str, Callable[..., Any]] = {}


def _register(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
        ALLOWED_FUNCS[name] = fn
        return fn

    return wrap


@_register("selected")
def _selected(value: object, needle: object) -> bool:
    """True if a space-separated ``select_multiple`` value contains ``needle``."""

    if value is None:
        return False
    if not isinstance(needle, str):
        return False
    tokens = str(value).split()
    return needle in tokens


@_register("isna")
def _isna(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float):
        import math

        return math.isnan(value)
    if isinstance(value, str):
        return value == ""
    return False


@_register("between")
def _between(value: object, low: object, high: object) -> bool:
    try:
        v = float(value)  # type: ignore[arg-type]
        lo = float(low)  # type: ignore[arg-type]
        hi = float(high)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return lo <= v <= hi


@_register("in_list")
def _in_list(value: object, options: object) -> bool:
    if not isinstance(options, list | tuple | set):
        return False
    return value in options


@_register("startswith")
def _startswith(value: object, prefix: object) -> bool:
    if not isinstance(value, str) or not isinstance(prefix, str):
        return False
    return value.startswith(prefix)


# Node types we are willing to execute. Anything else is a hard error.
_ALLOWED_NODES: tuple[type, ...] = (
    ast.Expression,
    ast.BoolOp,
    ast.UnaryOp,
    ast.Compare,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.List,
    ast.Tuple,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
)


def _validate(node: ast.AST) -> None:
    for child in ast.walk(node):
        if not isinstance(child, _ALLOWED_NODES):
            raise IndicatorError(
                f"Unsupported syntax in expression: {type(child).__name__}",
                suggest="Use only comparisons, and/or/not, in/not in, and the "
                "allowed helper functions.",
            )
        if isinstance(child, ast.Call) and (
            not isinstance(child.func, ast.Name) or child.func.id not in ALLOWED_FUNCS
        ):
            name = getattr(child.func, "id", "?")
            raise IndicatorError(
                f"Function call not allowed: {name}",
                suggest=f"Allowed: {', '.join(sorted(ALLOWED_FUNCS))}.",
            )


def parse_expression(source: str) -> ast.Expression:
    """Parse and validate ``source``. Returns the AST or raises IndicatorError."""

    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as exc:
        raise IndicatorError(
            f"Could not parse expression: {source!r}",
            suggest="Check quotes and parentheses.",
        ) from exc
    _validate(tree)
    return tree


_BOOL_OPS: dict[type, Callable[[Any, Any], bool]] = {
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


def _eval(node: ast.AST, context: dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval(node.body, context)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return context.get(node.id)
    if isinstance(node, ast.List | ast.Tuple):
        return [_eval(el, context) for el in node.elts]
    if isinstance(node, ast.BoolOp):
        values = [_eval(v, context) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        return any(values)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval(node.operand, context)
    if isinstance(node, ast.Compare):
        left = _eval(node.left, context)
        for op, comparator in zip(node.ops, node.comparators, strict=False):
            right = _eval(comparator, context)
            fn = _BOOL_OPS.get(type(op))
            if fn is None:
                raise IndicatorError(f"Operator not allowed: {type(op).__name__}")
            try:
                ok = fn(left, right)
            except TypeError:
                # Comparing None/NaN to a number: treat as False so filters
                # don't blow up on missing data.
                return False
            if not ok:
                return False
            left = right
        return True
    if isinstance(node, ast.Call):
        name = node.func.id  # type: ignore[attr-defined]
        args = [_eval(a, context) for a in node.args]
        return ALLOWED_FUNCS[name](*args)
    raise IndicatorError(f"Cannot evaluate node: {type(node).__name__}")


def evaluate(source: str, context: dict[str, Any]) -> bool:
    """Evaluate a parsed expression against a per-row context dict.

    Falsy result for a row means that row is excluded from the numerator (or
    denominator, depending on where this expression was used).
    """

    tree = parse_expression(source)
    return bool(_eval(tree, context))


def referenced_columns(source: str) -> set[str]:
    """Return the set of column names referenced by ``source``."""

    try:
        tree = parse_expression(source)
    except IndicatorError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in ALLOWED_FUNCS:
            # ``True``/``False``/``None`` are ``ast.Constant`` in py3.11+, so Name
            # here is always a column reference (functions are handled above).
            names.add(node.id)
    return names

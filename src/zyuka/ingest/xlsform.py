"""XLSForm parser.

An XLSForm is an Excel workbook describing an ODK / Kobo survey: a ``survey``
sheet lists one question per row (``type``, ``name``, ``label``, ``constraint``,
``relevant`` etc.) and a ``choices`` sheet lists multiple-choice options.

This module parses a form into a :class:`XLSForm` dataclass holding:

- questions keyed by name, with type, label and expression strings,
- a code→label map per ``select_one`` / ``select_multiple`` field.

Constraint and skip-logic expressions are translated into a small tree we can
evaluate safely against a DataFrame (see :mod:`zyuka.quality.constraints`).
Unsupported constructs raise :class:`UnsupportedExpression` which the quality
checker catches and reports as a warning, never as an error.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook

from zyuka.errors import IngestError


class UnsupportedExpression(Exception):  # noqa: N818  (kept for API clarity)
    """Raised when an XLSForm expression contains syntax we don't support."""


@dataclass(frozen=True)
class Question:
    name: str
    type: str
    label: str
    constraint: str | None = None
    relevant: str | None = None
    choice_list: str | None = None


@dataclass
class XLSForm:
    questions: dict[str, Question] = field(default_factory=dict)
    choices: dict[str, dict[str, str]] = field(default_factory=dict)

    def label_for(self, question_name: str, code: str) -> str:
        q = self.questions.get(question_name)
        if q is None or q.choice_list is None:
            return code
        return self.choices.get(q.choice_list, {}).get(code, code)


def parse_xlsform(path: Path) -> XLSForm:
    if not path.exists():
        raise IngestError(f"XLSForm not found: {path}", suggest="Check the path and try again.")
    try:
        wb = load_workbook(path, data_only=True, read_only=True)
    except Exception as exc:
        raise IngestError(
            f"Could not open XLSForm {path.name}: {exc}",
            suggest="Open the file in Excel to check it is not corrupted.",
        ) from exc

    survey_sheet = _get_sheet(wb, "survey")
    choices_sheet = _get_sheet(wb, "choices")

    form = XLSForm()
    form.choices = _read_choices(choices_sheet) if choices_sheet else {}
    form.questions = _read_survey(survey_sheet) if survey_sheet else {}
    return form


def _get_sheet(wb: object, name: str) -> object | None:
    sheetnames = getattr(wb, "sheetnames", [])
    for s in sheetnames:
        if s.lower() == name.lower():
            return wb[s]  # type: ignore[index, no-any-return]
    return None


def _read_survey(sheet: object) -> dict[str, Question]:
    rows = _rows(sheet)
    if not rows:
        return {}
    header = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
    cols = {h: i for i, h in enumerate(header)}
    required = {"type", "name"}
    if not required.issubset(cols):
        return {}
    out: dict[str, Question] = {}
    for row in rows[1:]:
        if not row or row[cols["name"]] in (None, ""):
            continue
        qtype = str(row[cols["type"]]).strip()
        qname = str(row[cols["name"]]).strip()
        label = str(row[cols.get("label", -1)] or "") if "label" in cols else ""
        constraint = _cell_or_none(row, cols.get("constraint"))
        relevant = _cell_or_none(row, cols.get("relevant"))
        choice_list: str | None = None
        m = re.match(r"^(select_one|select_multiple)\s+(\S+)", qtype)
        if m:
            qtype = m.group(1)
            choice_list = m.group(2)
        out[qname] = Question(
            name=qname,
            type=qtype,
            label=label,
            constraint=constraint,
            relevant=relevant,
            choice_list=choice_list,
        )
    return out


def _read_choices(sheet: object) -> dict[str, dict[str, str]]:
    rows = _rows(sheet)
    if not rows:
        return {}
    header = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
    cols = {h: i for i, h in enumerate(header)}
    if not {"list_name", "name"}.issubset(cols):
        return {}
    out: dict[str, dict[str, str]] = {}
    for row in rows[1:]:
        if not row or row[cols["list_name"]] in (None, ""):
            continue
        list_name = str(row[cols["list_name"]]).strip()
        code = str(row[cols["name"]]).strip()
        label = str(row[cols.get("label", -1)] or "") if "label" in cols else code
        out.setdefault(list_name, {})[code] = label
    return out


def _rows(sheet: object) -> list[list[object]]:
    iter_rows = getattr(sheet, "iter_rows", None)
    if iter_rows is None:
        return []
    return [[c.value for c in row] for row in iter_rows()]


def _cell_or_none(row: list[object], idx: int | None) -> str | None:
    if idx is None or idx >= len(row):
        return None
    v = row[idx]
    if v in (None, ""):
        return None
    return str(v).strip()


# ---------------------------------------------------------------------------
# Expression translation
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""(?x)
    \s+                                 |   # whitespace
    (?P<op>!=|>=|<=|=|>|<)              |   # comparisons
    (?P<logic>and|or|not)\b             |   # boolean
    (?P<fn>selected)\(                  |   # supported function
    (?P<dot>\.)                         |   # . means "current field value"
    (?P<paren>[()])                     |   # grouping
    (?P<comma>,)                        |
    (?P<str>'[^']*'|"[^"]*")            |   # single/double quoted string
    (?P<num>-?\d+(?:\.\d+)?)            |   # number
    (?P<ident>\$\{[^}]+\}|[A-Za-z_][\w]*)   # $$ reference or identifier
    """
)


def translate_expression(expr: str, current_field: str | None = None) -> str:
    """Translate a (limited) XLSForm expression into a pandas ``query`` string.

    Supported: comparisons, boolean operators, ``.`` for the current field,
    ``${name}`` references and ``selected(., 'value')`` for select_multiple.
    Any other construct raises :class:`UnsupportedExpression`.
    """

    tokens: list[str] = []
    pos = 0
    while pos < len(expr):
        m = _TOKEN_RE.match(expr, pos)
        if m is None:
            raise UnsupportedExpression(f"unexpected character at pos {pos}: {expr[pos]!r}")
        pos = m.end()
        if m.lastgroup is None:  # whitespace
            continue
        group = m.lastgroup
        text = m.group(group)
        if group == "op":
            tokens.append("==" if text == "=" else text)
        elif group == "logic":
            tokens.append({"and": " and ", "or": " or ", "not": " not "}[text])
        elif group == "fn":
            if text != "selected":
                raise UnsupportedExpression(f"unsupported function: {text}")
            tokens.append("@zyuka_selected(")
        elif group == "dot":
            if current_field is None:
                raise UnsupportedExpression("'.' used outside the context of a field")
            tokens.append(f"`{current_field}`")
        elif group == "paren":
            tokens.append(text)
        elif group == "comma":
            tokens.append(",")
        elif group in {"str", "num"}:
            tokens.append(text)
        elif group == "ident":
            name = text[2:-1] if text.startswith("${") and text.endswith("}") else text
            tokens.append(f"`{name}`")
    return "".join(tokens).strip()

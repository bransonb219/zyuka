"""Persist cleaning decisions so re-runs don't re-ask the user.

Each approved :class:`~zyuka.quality.remediate.CleaningDecision` becomes
a *rule* keyed by ``(reason, column, kind, params_signature)``. On the
next round / re-run, matching proposals are pre-approved and the user
sees "last time you capped age>95 at 95 — approve again?" instead of
starting from scratch.

The file lives at ``<project>/.zyuka/cleaning_rules.json``; it is a
plain JSON document (not JSONL) so a human can read and edit it. No
personal data is stored — only column names, reasons, fix kinds and
parameters.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from zyuka.quality.remediate import VALID_KINDS, CleaningDecision, FixAction

CURRENT_VERSION = 1


@dataclass
class CleaningRule:
    """A persisted fix for a specific (reason, column) pair."""

    reason: str
    column: str
    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    approved_at: str = ""
    approved_count: int = 1

    @property
    def signature(self) -> str:
        """Stable short hash for identity checks across edits."""

        payload = json.dumps(
            {
                "reason": self.reason,
                "column": self.column,
                "kind": self.kind,
                "params": self.params,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "column": self.column,
            "kind": self.kind,
            "params": self.params,
            "approved_at": self.approved_at,
            "approved_count": self.approved_count,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CleaningRule:
        kind = str(data.get("kind", ""))
        if kind not in VALID_KINDS:
            raise ValueError(f"Unknown cleaning fix kind: {kind!r}")
        return cls(
            reason=str(data["reason"]),
            column=str(data["column"]),
            kind=kind,
            params=dict(data.get("params") or {}),
            approved_at=str(data.get("approved_at", "")),
            approved_count=int(data.get("approved_count", 1)),
        )


@dataclass
class CleaningRules:
    """In-memory view of the ``cleaning_rules.json`` file."""

    rules: list[CleaningRule] = field(default_factory=list)
    version: int = CURRENT_VERSION

    def find(self, reason: str, column: str) -> CleaningRule | None:
        for rule in self.rules:
            if rule.reason == reason and rule.column == column:
                return rule
        return None

    def upsert(self, decision: CleaningDecision) -> CleaningRule:
        """Add or update the rule implied by an approved decision."""

        if decision.status not in {"approved", "modified"}:
            raise ValueError(f"Cannot persist a {decision.status!r} decision as a rule.")

        action = decision.action
        existing = self.find(action.reason, action.column)
        now = datetime.now(UTC).isoformat(timespec="seconds")

        if existing is not None:
            existing.kind = decision.effective_kind
            existing.params = dict(decision.effective_params)
            existing.approved_at = now
            existing.approved_count += 1
            return existing

        rule = CleaningRule(
            reason=action.reason,
            column=action.column,
            kind=decision.effective_kind,
            params=dict(decision.effective_params),
            approved_at=now,
            approved_count=1,
        )
        self.rules.append(rule)
        return rule

    def to_json(self) -> str:
        return json.dumps(
            {
                "version": self.version,
                "rules": [r.to_dict() for r in self.rules],
            },
            indent=2,
            sort_keys=False,
        )


def rules_path(project_dir: Path) -> Path:
    """Location of the cleaning-rules file for a project."""

    return project_dir / ".zyuka" / "cleaning_rules.json"


def load_rules(project_dir: Path) -> CleaningRules:
    """Read the project's saved cleaning rules; return empty on absence."""

    path = rules_path(project_dir)
    if not path.exists():
        return CleaningRules()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return CleaningRules()

    version = int(data.get("version", CURRENT_VERSION))
    rules: list[CleaningRule] = []
    for entry in data.get("rules", []):
        try:
            rules.append(CleaningRule.from_dict(entry))
        except (KeyError, ValueError):
            continue
    return CleaningRules(rules=rules, version=version)


def save_rules(project_dir: Path, rules: CleaningRules) -> Path:
    """Write the cleaning rules atomically. Returns the file path."""

    path = rules_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(rules.to_json(), encoding="utf-8")
    tmp.replace(path)
    return path


def preapproved_decisions(actions: list[FixAction], rules: CleaningRules) -> list[CleaningDecision]:
    """Return decisions auto-filled from the rules file for matching actions.

    Non-matching actions are returned with no decision — callers decide
    whether to surface them for user approval.
    """

    decisions: list[CleaningDecision] = []
    for action in actions:
        rule = rules.find(action.reason, action.column)
        if rule is None:
            continue
        decisions.append(
            CleaningDecision(
                action=action,
                status="modified" if rule.kind != action.kind else "approved",
                override_kind=rule.kind,
                override_params=dict(rule.params),
            )
        )
    return decisions

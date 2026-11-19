"""`zyuka clean` — turn quality flags into a cleaned dataset.

Two modes:

* ``--apply-rules`` (default) replays any decisions saved in
  ``.zyuka/cleaning_rules.json`` and writes a cleaned CSV. Non-matching
  actions are left for the user to review in the GUI.
* ``--interactive`` prompts once per flag group. Approved choices are
  appended to the rules file so the next round / re-run is quieter.

The command never mutates the raw export; the cleaned dataset is
written to ``outputs/clean/clean_{round}.csv`` alongside a
``review_{round}.csv`` listing any flag-only entries.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from zyuka.quality.remediate import (
    CleaningDecision,
    CleaningResult,
    FixAction,
    apply_decisions,
    propose_actions,
)
from zyuka.quality.report import run_quality
from zyuka.quality.rules import (
    load_rules,
    preapproved_decisions,
    save_rules,
)

console = Console()


def clean(
    data: Annotated[Path, typer.Argument(help="CSV or XLSX export.")],
    project: Annotated[
        Path,
        typer.Option("--project", help="Project directory (contains zyuka.yml)."),
    ] = Path("."),
    round_name: Annotated[str, typer.Option("--round", help="Round name.")] = "baseline",
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive/--apply-rules",
            help="Prompt once per flag group (default: replay saved rules only).",
        ),
    ] = False,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Where to write clean_{round}.csv."),
    ] = None,
) -> None:
    """Apply approved cleaning actions and write a cleaned round."""

    from zyuka.ingest.rounds import load_round

    df = load_round(data, round_name)
    quality = run_quality(df)
    actions = propose_actions(df, quality.flags, quality.per_column_missing)
    if not actions:
        console.print("[green]Nothing to clean — no quality flags detected.[/green]")
        return

    rules = load_rules(project)
    saved = preapproved_decisions(actions, rules)
    saved_keys = {(d.action.reason, d.action.column) for d in saved}

    pending = [a for a in actions if (a.reason, a.column) not in saved_keys]

    decisions: list[CleaningDecision] = list(saved)
    if interactive and pending:
        decisions.extend(_prompt(pending))
    elif pending:
        _print_pending(pending)

    result = apply_decisions(df, decisions)

    out_dir = project / "outputs" / "clean"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out or out_dir / f"clean_{round_name}.csv"
    result.cleaned.to_csv(out_path, index=False)

    if not result.review_rows.empty:
        review_path = out_dir / f"review_{round_name}.csv"
        result.review_rows.to_csv(review_path, index=False)

    if interactive:
        for decision in decisions:
            if decision.status in {"approved", "modified"}:
                rules.upsert(decision)
        save_rules(project, rules)

    _summarise(result, out_path, saved, pending, interactive=interactive)


def _print_pending(pending: list[FixAction]) -> None:
    table = Table(title="Flags awaiting decision")
    table.add_column("Reason")
    table.add_column("Column")
    table.add_column("Rows", justify="right")
    table.add_column("Default fix")
    for action in pending:
        table.add_row(action.reason, action.column, str(len(action.row_indices)), action.kind)
    console.print(table)
    console.print(
        "[yellow]No saved rule covers these. Run with [bold]--interactive[/bold] or "
        "approve them in the GUI.[/yellow]"
    )


def _prompt(pending: list[FixAction]) -> list[CleaningDecision]:
    """Ask the user one question per action and return the decisions."""

    out: list[CleaningDecision] = []
    for action in pending:
        console.rule(f"[bold]{action.reason}[/bold] · {action.column}")
        console.print(action.rationale or "—")
        console.print(f"[dim]Rows affected: {len(action.row_indices)}[/dim]")
        console.print(f"[dim]Default fix: [bold]{action.kind}[/bold] {dict(action.params)}[/dim]")
        choice = Prompt.ask(
            "Approve this fix?",
            choices=["y", "n", "s"],
            default="y",
            show_choices=True,
        )
        status = {"y": "approved", "n": "rejected", "s": "rejected"}[choice]
        out.append(CleaningDecision(action=action, status=status))
    return out


def _summarise(
    result: CleaningResult,
    out_path: Path,
    saved: list[CleaningDecision],
    pending: list[FixAction],
    *,
    interactive: bool,
) -> None:
    table = Table(title="Cleaning summary")
    table.add_column("Action")
    table.add_column("Rows", justify="right")
    for name, count in result.summary.items():
        table.add_row(name, str(count))
    console.print(table)
    console.print(f"[green]Wrote[/green] {out_path}")
    console.print(f"[dim]Replayed from rules:[/dim] {len(saved)}")
    console.print(f"[dim]Awaiting decision:[/dim] {len(pending) if not interactive else 0}")

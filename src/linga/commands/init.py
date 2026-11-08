"""`linga init` — guided project setup.

Real implementation lands in milestone 8. For now this writes the templates
non-interactively when ``--yes`` is passed, so other commands have something
to read against.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()

_LINGA_YML_TEMPLATE = """# linga.yml — Linga project configuration
organisation: "Example NGO"
programme: "Programme name"
data_controller_contact: "dpo@example.org"
retention_days: 1825
key_path: "{key_path}"

protection:
  small_cell_threshold: 5
  gps_decimals: 1
  drop_free_text: true
  keep_columns: []

traffic_light:
  on_track: 80.0
  at_risk: 50.0

consent_column: "demographics/consent"
"""

_LOGFRAME_YML_TEMPLATE = """# logframe.yml — logframe for your programme.
# Each indicator has: code, name, type, numerator, optional denominator,
# disaggregations, targets per round, and metadata.
goal: "Improved wellbeing of target households"
goal_indicators:
  - code: "G1"
    name: "People reached"
    type: "count_unique"
    numerator: "pid_seed != ''"
    disaggregations: ["sex", "province"]
    targets: { baseline: 150, midline: 300, endline: 500 }
    unit: "people"
outcomes:
  - code: "OC1"
    name: "Household incomes increased"
    indicators:
      - code: "OC1.1"
        name: "Proportion with an income source"
        type: "proportion"
        numerator: "livelihoods/has_income_source == 'yes'"
        denominator: "pid_seed != ''"
        disaggregations: ["sex"]
        targets: { baseline: 0.4, midline: 0.6, endline: 0.75 }
    outputs:
      - code: "OP1.1"
        name: "Livelihoods training delivered"
        indicators:
          - code: "OP1.1.1"
            name: "People trained"
            type: "count"
            numerator: "training/attended == 'yes'"
            disaggregations: ["sex", "province"]
            targets: { baseline: 50, midline: 150, endline: 300 }
"""


def init(
    directory: Annotated[Path, typer.Argument(help="Project directory.")] = Path("."),
    key_path: Annotated[
        Path | None,
        typer.Option("--key-path", help="Where the key file will live (outside the project)."),
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Non-interactive.")] = False,
) -> None:
    """Scaffold ``linga.yml`` + ``logframe.yml`` and nominate a key file path."""

    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)

    default_key = (directory.parent / ".linga-keys" / f"{directory.name}.key").resolve()
    key = key_path.resolve() if key_path else default_key

    linga_yml = directory / "linga.yml"
    logframe_yml = directory / "logframe.yml"

    if not yes and (linga_yml.exists() or logframe_yml.exists()):
        console.print(
            "[yellow]linga.yml or logframe.yml already exists; refusing to overwrite.[/yellow]"
        )
        raise typer.Exit(code=1)

    linga_yml.write_text(_LINGA_YML_TEMPLATE.format(key_path=key), encoding="utf-8")
    logframe_yml.write_text(_LOGFRAME_YML_TEMPLATE, encoding="utf-8")

    console.print(f"[green]Wrote[/green] {linga_yml}")
    console.print(f"[green]Wrote[/green] {logframe_yml}")
    console.print(f"[cyan]Key path (not created yet):[/cyan] {key}")
    console.print("Next: `linga key generate` to create the key, then `linga demo` to try it.")

"""`zyuka demo` — scaffold a throwaway project and run the full pipeline.

Creates synthetic 3-round data, a minimal ``zyuka.yml`` and ``logframe.yml``,
generates a key file outside the project directory and runs the pipeline so a
first-time user ends up looking at a finished HTML report and Excel IPTT.

Everything happens under the directory passed as ``out_dir`` (default
``./zyuka-demo``). Nothing leaves the machine.
"""

from __future__ import annotations

from pathlib import Path

from zyuka.commands.init import _LOGFRAME_YML_TEMPLATE, _ZYUKA_YML_TEMPLATE
from zyuka.pipeline import PipelineResult, run_pipeline
from zyuka.security.keys import generate_key
from zyuka.synthetic import ROUND_NAMES, write_rounds


def _write_project_files(project_dir: Path, key_path: Path) -> None:
    (project_dir / "zyuka.yml").write_text(
        _ZYUKA_YML_TEMPLATE.format(
            organisation="Example NGO",
            programme="Demo Programme",
            data_controller="dpo@example.org",
            retention_days=1825,
            key_path=key_path.as_posix(),
            small_cell=5,
        ),
        encoding="utf-8",
    )
    (project_dir / "logframe.yml").write_text(_LOGFRAME_YML_TEMPLATE, encoding="utf-8")


def run_demo(out_dir: Path = Path("zyuka-demo"), open_report: bool = False) -> Path:
    """Generate data, write config, run the pipeline and return the HTML path."""

    project_dir = Path(out_dir).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)

    data_dir = project_dir / "data"
    key_path = project_dir / ".zyuka-keys" / "demo.key"
    key_path.parent.mkdir(parents=True, exist_ok=True)

    if not key_path.exists():
        generate_key(key_path)

    write_rounds(data_dir)
    _write_project_files(project_dir, key_path)

    result: PipelineResult = run_pipeline(
        project_dir=project_dir,
        rounds=list(ROUND_NAMES),
        open_report=open_report,
    )
    return result.report_html

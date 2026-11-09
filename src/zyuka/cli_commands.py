"""Subcommand registration.

Each later milestone appends real commands here. Registration is explicit so
new commands can't accidentally import heavy deps at module-load time.
"""

from __future__ import annotations

import typer


def register(app: typer.Typer) -> None:
    """Attach every Zyuka subcommand to ``app``."""

    # Imports are local so `zyuka --version` stays fast.
    from zyuka.cli import _handle
    from zyuka.commands import (
        audit as audit_cmd,
    )
    from zyuka.commands import (
        check as check_cmd,
    )
    from zyuka.commands import (
        compute as compute_cmd,
    )
    from zyuka.commands import (
        decrypt as decrypt_cmd,
    )
    from zyuka.commands import (
        demo as demo_cmd,
    )
    from zyuka.commands import (
        docs as docs_cmd,
    )
    from zyuka.commands import (
        gui as gui_cmd,
    )
    from zyuka.commands import (
        init as init_cmd,
    )
    from zyuka.commands import (
        key as key_cmd,
    )
    from zyuka.commands import (
        protect as protect_cmd,
    )
    from zyuka.commands import (
        report as report_cmd,
    )
    from zyuka.commands import (
        retention as retention_cmd,
    )
    from zyuka.commands import (
        run as run_cmd,
    )
    from zyuka.commands import (
        scan as scan_cmd,
    )
    from zyuka.commands import (
        subject as subject_cmd,
    )

    app.command("init", help="Create zyuka.yml, logframe.yml and a key path.")(
        _handle(init_cmd.init)
    )
    app.command("demo", help="Run the full pipeline on synthetic data.")(_handle(demo_cmd.demo))
    app.command("run", help="Run check → scan → protect → compute → report → audit.")(
        _handle(run_cmd.run)
    )
    app.command("check", help="Data-quality checks on a round.")(_handle(check_cmd.check))
    app.command("scan", help="Scan for PII and sensitive fields.")(_handle(scan_cmd.scan))
    app.command("protect", help="Pseudonymise, minimise and generalise a round.")(
        _handle(protect_cmd.protect)
    )
    app.command("compute", help="Compute indicators from protected data.")(
        _handle(compute_cmd.compute)
    )
    app.command("report", help="Render HTML report and Excel IPTT.")(_handle(report_cmd.report))
    app.command("gui", help="Launch the local Streamlit app.")(_handle(gui_cmd.gui))
    app.command("decrypt", help="Decrypt a .enc file produced with --encrypt.")(
        _handle(decrypt_cmd.decrypt)
    )

    key_app = typer.Typer(help="Key lifecycle: generate, rotate, verify.")
    key_app.command("generate")(_handle(key_cmd.generate))
    key_app.command("rotate")(_handle(key_cmd.rotate))
    key_app.command("verify")(_handle(key_cmd.verify))
    app.add_typer(key_app, name="key")

    audit_app = typer.Typer(help="Audit trail: show, verify.")
    audit_app.command("show")(_handle(audit_cmd.show))
    audit_app.command("verify")(_handle(audit_cmd.verify))
    app.add_typer(audit_app, name="audit")

    subject_app = typer.Typer(help="Data-subject rights: find, erase.")
    subject_app.command("find")(_handle(subject_cmd.find))
    subject_app.command("erase")(_handle(subject_cmd.erase))
    app.add_typer(subject_app, name="subject")

    retention_app = typer.Typer(help="Retention: check, purge.")
    retention_app.command("check")(_handle(retention_cmd.check))
    retention_app.command("purge")(_handle(retention_cmd.purge))
    app.add_typer(retention_app, name="retention")

    docs_app = typer.Typer(help="Generate compliance documents.")
    docs_app.command("dpia")(_handle(docs_cmd.dpia))
    docs_app.command("consent")(_handle(docs_cmd.consent))
    app.add_typer(docs_app, name="docs")

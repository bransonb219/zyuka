"""Subcommand registration.

Each later milestone appends real commands here. Registration is explicit so
new commands can't accidentally import heavy deps at module-load time.
"""

from __future__ import annotations

import typer


def register(app: typer.Typer) -> None:
    """Attach every Linga subcommand to ``app``."""

    # Imports are local so `linga --version` stays fast.
    from linga.commands import (
        audit as audit_cmd,
    )
    from linga.commands import (
        check as check_cmd,
    )
    from linga.commands import (
        compute as compute_cmd,
    )
    from linga.commands import (
        decrypt as decrypt_cmd,
    )
    from linga.commands import (
        demo as demo_cmd,
    )
    from linga.commands import (
        docs as docs_cmd,
    )
    from linga.commands import (
        gui as gui_cmd,
    )
    from linga.commands import (
        init as init_cmd,
    )
    from linga.commands import (
        key as key_cmd,
    )
    from linga.commands import (
        protect as protect_cmd,
    )
    from linga.commands import (
        report as report_cmd,
    )
    from linga.commands import (
        retention as retention_cmd,
    )
    from linga.commands import (
        run as run_cmd,
    )
    from linga.commands import (
        scan as scan_cmd,
    )
    from linga.commands import (
        subject as subject_cmd,
    )

    app.command("init", help="Create linga.yml, logframe.yml and a key path.")(init_cmd.init)
    app.command("demo", help="Run the full pipeline on synthetic data.")(demo_cmd.demo)
    app.command("run", help="Run check → scan → protect → compute → report → audit.")(run_cmd.run)
    app.command("check", help="Data-quality checks on a round.")(check_cmd.check)
    app.command("scan", help="Scan for PII and sensitive fields.")(scan_cmd.scan)
    app.command("protect", help="Pseudonymise, minimise and generalise a round.")(
        protect_cmd.protect
    )
    app.command("compute", help="Compute indicators from protected data.")(compute_cmd.compute)
    app.command("report", help="Render HTML report and Excel IPTT.")(report_cmd.report)
    app.command("gui", help="Launch the local Streamlit app.")(gui_cmd.gui)
    app.command("decrypt", help="Decrypt a .enc file produced with --encrypt.")(decrypt_cmd.decrypt)

    key_app = typer.Typer(help="Key lifecycle: generate, rotate, verify.")
    key_app.command("generate")(key_cmd.generate)
    key_app.command("rotate")(key_cmd.rotate)
    key_app.command("verify")(key_cmd.verify)
    app.add_typer(key_app, name="key")

    audit_app = typer.Typer(help="Audit trail: show, verify.")
    audit_app.command("show")(audit_cmd.show)
    audit_app.command("verify")(audit_cmd.verify)
    app.add_typer(audit_app, name="audit")

    subject_app = typer.Typer(help="Data-subject rights: find, erase.")
    subject_app.command("find")(subject_cmd.find)
    subject_app.command("erase")(subject_cmd.erase)
    app.add_typer(subject_app, name="subject")

    retention_app = typer.Typer(help="Retention: check, purge.")
    retention_app.command("check")(retention_cmd.check)
    retention_app.command("purge")(retention_cmd.purge)
    app.add_typer(retention_app, name="retention")

    docs_app = typer.Typer(help="Generate compliance documents.")
    docs_app.command("dpia")(docs_cmd.dpia)
    docs_app.command("consent")(docs_cmd.consent)
    app.add_typer(docs_app, name="docs")

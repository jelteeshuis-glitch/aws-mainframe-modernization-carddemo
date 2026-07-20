"""Command-line entrypoints for each batch service (one per container image)."""

from __future__ import annotations

import sys

from . import config
from .db import create_schema, make_engine, session_scope
from .loader import load_all
from .services import combine, interest, posting, report, statement


def load_main(argv: list[str] | None = None) -> int:
    """Create the schema and load the fixed-width sample data."""
    engine = make_engine()
    create_schema(engine)
    with session_scope(engine) as session:
        counts = load_all(session, config.data_dir())
    print("LOAD complete:", counts)
    return 0


def posttran_main(argv: list[str] | None = None) -> int:
    """POSTTRAN / CBTRN02C."""
    engine = make_engine()
    create_schema(engine)
    with session_scope(engine) as session:
        result = posting.run(session)
    print(
        f"POSTTRAN complete: processed={result.processed} posted={result.posted} "
        f"rejected={result.rejected} return_code={result.return_code}"
    )
    return 0


def intcalc_main(argv: list[str] | None = None) -> int:
    """INTCALC / CBACT04C."""
    engine = make_engine()
    create_schema(engine)
    with session_scope(engine) as session:
        result = interest.run(session, parm_date=config.interest_parm_date())
    print(
        f"INTCALC complete: accounts_updated={result.accounts_updated} "
        f"interest_transactions={result.interest_transactions} "
        f"total_interest={result.total_interest}"
    )
    return 0


def combtran_main(argv: list[str] | None = None) -> int:
    """COMBTRAN / SORT + IDCAMS."""
    engine = make_engine()
    create_schema(engine)
    with session_scope(engine) as session:
        result = combine.run(session)
    print(f"COMBTRAN complete: merged={result.merged} total_transactions={result.total}")
    return 0


def creastmt_main(argv: list[str] | None = None) -> int:
    """CREASTMT / CBSTM03A — writes text + HTML statements to the output directory."""
    engine = make_engine()
    create_schema(engine)
    out = config.output_dir() / "statements"
    out.mkdir(parents=True, exist_ok=True)
    with session_scope(engine) as session:
        result = statement.run(session)
        for st in result.statements:
            (out / f"stmt_{st.acct_id}.txt").write_text(st.text_body, encoding="utf-8")
            (out / f"stmt_{st.acct_id}.html").write_text(st.html_body, encoding="utf-8")
    print(f"CREASTMT complete: statements={result.count} output_dir={out}")
    return 0


def tranrept_main(argv: list[str] | None = None) -> int:
    """TRANREPT / CBTRN03C — writes the transaction report to the output directory."""
    engine = make_engine()
    create_schema(engine)
    start, end = config.report_date_range()
    out = config.output_dir()
    out.mkdir(parents=True, exist_ok=True)
    with session_scope(engine) as session:
        result = report.run(session, start, end)
    report_path = out / "tranrept.txt"
    report_path.write_text(result.body, encoding="utf-8")
    print(f"TRANREPT complete: lines={result.lines} grand_total={result.grand_total} "
          f"output={report_path}")
    return 0


def pipeline_main(argv: list[str] | None = None) -> int:
    """Run the full pipeline in strict order in a single process (local orchestrator).

    Enforces POSTTRAN -> INTCALC -> COMBTRAN -> CREASTMT -> TRANREPT through real data
    dependencies: each stage only runs after the previous one has committed successfully,
    replacing the JCL chaining and the COBSWAIT timer. Intended for local / docker-compose
    execution; the AWS-native equivalent is orchestration/step_functions.asl.json.
    """
    rc = load_main(argv)
    if rc:
        return rc
    for step in (posttran_main, intcalc_main, combtran_main, creastmt_main, tranrept_main):
        rc = step(argv)
        if rc:
            print(f"PIPELINE aborted at {step.__name__} (rc={rc})")
            return rc
    print("PIPELINE complete")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(load_main())

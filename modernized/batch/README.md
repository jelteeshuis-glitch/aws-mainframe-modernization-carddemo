# CardDemo — Modernized Batch Pipeline

A cloud-native, container-based re-implementation of the CardDemo **core batch
processing** flow. It replaces JCL + COBOL + VSAM with Python services backed by
**PostgreSQL**, and replaces JCL job-chaining and the `COBSWAIT` (`WAITSTEP`) timer with
**real job dependencies** — AWS Step Functions for the cloud, docker-compose for local
runs.

This is an **additive demonstration**: nothing under `app/` is changed. The original
COBOL/JCL remains the reference implementation; this directory is the modern counterpart.

See [`BUSINESS_RULES.md`](BUSINESS_RULES.md) for the functional specification (validation
codes, posting/interest formulas, copybook field maps and decimal handling) that these
services preserve.

## Pipeline

```
POSTTRAN → INTCALC → COMBTRAN → CREASTMT → TRANREPT
```

Each stage runs only after the previous stage completes successfully — no timers.

| Original job / program | Modern service | CLI entrypoint | Container |
|------------------------|----------------|----------------|-----------|
| `POSTTRAN` / `CBTRN02C` | transaction posting | `carddemo-posttran` | `docker/posttran.Dockerfile` |
| `INTCALC` / `CBACT04C` | interest calculation | `carddemo-intcalc` | `docker/intcalc.Dockerfile` |
| `COMBTRAN` / `SORT`+`IDCAMS` | transaction merge/normalization | `carddemo-combtran` | `docker/combtran.Dockerfile` |
| `CREASTMT` / `CBSTM03A` | statement generation (text + HTML) | `carddemo-creastmt` | `docker/creastmt.Dockerfile` |
| `TRANREPT` / `CBTRN03C` | transaction detail report | `carddemo-tranrept` | `docker/tranrept.Dockerfile` |
| `WAITSTEP` / `COBSWAIT` | **removed** — replaced by Step Functions `Next` / compose `depends_on` | — | — |
| VSAM refresh (`IDCAMS REPRO`) | fixed-width sample-data loader | `carddemo-load` | `docker/base.Dockerfile` |

## Layout

```
modernized/batch/
├── BUSINESS_RULES.md          # functional spec derived from the COBOL
├── README.md
├── pyproject.toml             # package + pinned deps + ruff/pytest config
├── schema/schema.sql          # PostgreSQL DDL (mirrors the SQLAlchemy models)
├── src/carddemo_batch/
│   ├── copybook.py            # fixed-width parsing + zoned-decimal overpunch
│   ├── models.py              # SQLAlchemy ORM (relational schema from copybooks)
│   ├── db.py, config.py, loader.py, cli.py
│   └── services/              # posting, interest, combine, statement, report
├── orchestration/
│   ├── step_functions.asl.json  # AWS Step Functions state machine (ECS/Fargate tasks)
│   └── run_pipeline.py          # local orchestrator (strict order)
├── docker/                    # one Dockerfile per service (+ base image)
├── docker-compose.yml         # local ordered pipeline with PostgreSQL
└── tests/                     # unit + integration tests (use app/data fixtures)
```

## Data model

The PostgreSQL schema is derived directly from the copybooks in `app/cpy/`
(see the field maps in `BUSINESS_RULES.md`). Money fields use `NUMERIC(14,2)` and all
monetary arithmetic uses Python `Decimal` — never floating point — to preserve the exact
`PIC S9(n)V99` semantics of the COMP-3/zoned-decimal fields. The DDL in
`schema/schema.sql` is kept in sync with `src/carddemo_batch/models.py` (the ORM models
are the source of truth used by both PostgreSQL and the test suite).

## Run locally with docker-compose (PostgreSQL)

```bash
cd modernized/batch
docker compose up --build
```

This starts PostgreSQL, loads the sample data from `app/data/ASCII`, then runs the five
stages in order (each `depends_on` the previous stage completing successfully). Generated
statements and the transaction report land in `modernized/batch/output/`.

Re-run a single stage:

```bash
docker compose run --rm tranrept
```

## Run locally without Docker

Requires Python 3.10+.

```bash
cd modernized/batch
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

# Option A — SQLite, zero infrastructure (great for a quick demo):
export DATABASE_URL="sqlite+pysqlite:///carddemo.db"
export CARDDEMO_OUTPUT_DIR=output
carddemo-pipeline            # load + all five stages, in order

# Option B — PostgreSQL:
export DATABASE_URL="postgresql+psycopg2://carddemo:carddemo@localhost:5432/carddemo"
psql "$DATABASE_URL" -f schema/schema.sql   # optional; services also create tables
carddemo-load
carddemo-posttran && carddemo-intcalc && carddemo-combtran \
  && carddemo-creastmt && carddemo-tranrept
```

Configuration (all optional) is via environment variables — see
[`config.py`](src/carddemo_batch/config.py): `DATABASE_URL` (or `PGHOST`/`PGPORT`/
`PGUSER`/`PGPASSWORD`/`PGDATABASE`), `CARDDEMO_DATA_DIR`, `CARDDEMO_OUTPUT_DIR`,
`CARDDEMO_PARM_DATE` (INTCALC run date), `CARDDEMO_REPORT_START`/`CARDDEMO_REPORT_END`.

## AWS Step Functions

`orchestration/step_functions.asl.json` is an Amazon States Language state machine that
runs each service as an ECS/Fargate task and chains them with `Next` (plus `Retry` /
`Catch` for failure handling) — the `WAITSTEP`/`COBSWAIT` timer has no equivalent state.
Substitute your infra ARNs for the `${...}` placeholders (`EcsClusterArn`, the per-service
`*TaskDefinitionArn`, `SubnetId`) when deploying.

## Tests

```bash
cd modernized/batch
pip install -e ".[dev]"
pytest              # unit + integration
ruff check .        # lint
```

The suite regresses the modern services against the COBOL behaviour: overpunch decoding,
each reject code (100–103) and the expiry-over-limit precedence, credit/debit cycle
updates, transaction-category balance create/increment, the interest formula + generated
transaction fields, the `DEFAULT` rate fallback, account finalization/cycle reset,
statement grouping per card with HTML escaping, and a full end-to-end pipeline run over
the `app/data/ASCII` sample fixtures.

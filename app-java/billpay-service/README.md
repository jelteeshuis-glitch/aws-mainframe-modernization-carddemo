# Bill Payment regression harness (`billpay-service`)

A Java regression / characterization harness for the online Bill Payment COBOL
program **`COBIL00C`** (transaction `CB00`, map `COBIL0A`). It exists so the
Bill Payment logic can be **refactored safely** — the JUnit suite pins the
current, documented COBOL behaviour, and any change that alters it turns a test
red.

## What it is

- `service/BillPaymentService` — a faithful, seam-friendly Java port of
  `COBIL00C`'s `PROCESS-ENTER-KEY` logic (same validation order, business
  rules, generated record values, and verbatim message text).
- `model/` — `Account`, `CardXref`, `Transaction` mirroring copybooks
  `CVACT01Y`, `CVACT03Y`, `CVTRA05Y`.
- `repository/` — interfaces (`AccountRepository`, `CardXrefRepository`,
  `TransactionRepository`) that isolate the CICS/VSAM file operations behind
  seams, so behaviour can be tested without a CICS region.
- `src/test/.../support/` — in-memory VSAM stand-ins with fault injection to
  reproduce the non-normal CICS responses (`NOTFND`, `DUPKEY`/`DUPREC`, generic
  errors).
- `BillPaymentServiceRegressionTest` — 26 characterization tests.

## Behaviour locked in (from `COBIL00C`)

| Rule | Source |
|---|---|
| Account id must not be blank | `COBIL00C:159-167` |
| Confirmation flag: `Y`/`y` pays, `N`/`n` cancels, blank prompts, else invalid | `:173-191` |
| Balance must be `> 0` ("nothing to pay") | `:197-206` |
| Payment is always the **full** current balance | `:224,234` |
| Transaction: type `02`, category `2`, source `POS TERM`, desc `BILL PAYMENT - ONLINE`, merchant `999999999`/`BILL PAYMENT`/`N/A`/`N/A` | `:220-229` |
| Next tran id = last id + 1 (1 when file empty) | `:212-217,487-488` |
| Balance reduced by amount and account rewritten | `:234-235,377-403` |
| Success / error message text | `:361-543` |

> Fidelity note: `COBIL00C` writes the transaction **before** rewriting the
> account balance, with no rollback if the rewrite fails. The harness preserves
> this (see `FailurePaths.accountRewriteError`) rather than "fixing" it, so the
> tests describe the program as it is today.

## Run

```bash
cd app-java/billpay-service
mvn test
```

Requires JDK 17+ and Maven. No CICS, VSAM, or database is needed.

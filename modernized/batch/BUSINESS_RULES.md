# CardDemo Batch — Business Rules

This document captures the business rules of the CardDemo core batch programs, derived
directly from the COBOL `PROCEDURE DIVISION` of the original programs and the field
definitions in the copybooks under `app/cpy/`. It is the functional specification that
the modernized Python services in `modernized/batch/` re-implement **without changing
behaviour**.

Source programs analysed:

| Program | JCL job | Function |
|---------|---------|----------|
| `app/cbl/CBTRN02C.cbl` | `POSTTRAN` | Post daily transactions |
| `app/cbl/CBACT04C.cbl` | `INTCALC`  | Interest calculation |
| `SORT` (`app/jcl/COMBTRAN.jcl`) | `COMBTRAN` | Combine transaction files |
| `app/cbl/CBSTM03A.CBL` (+ `CBSTM03B.CBL`) | `CREASTMT` | Generate account statements |
| `app/cbl/CBTRN03C.cbl` | `TRANREPT` | Transaction detail report |

---

## 1. Record layouts and data types

All original files are fixed-width records. Numeric money/rate fields are **signed
zoned decimal** with the sign carried in the last byte as an *overpunch* character
(COBOL `PIC S9(n)V99` `DISPLAY`). Counts / ids are **unsigned zoned decimal**
(`PIC 9(n)`). `V99` means the last two digits are implied decimals (no physical
decimal point).

### Zoned-decimal overpunch table

The last byte of a signed field encodes both the least-significant digit and the sign:

| Digit | Positive | Negative |
|------:|:--------:|:--------:|
| 0 | `{` | `}` |
| 1 | `A` | `J` |
| 2 | `B` | `K` |
| 3 | `C` | `L` |
| 4 | `D` | `M` |
| 5 | `E` | `N` |
| 6 | `F` | `O` |
| 7 | `G` | `P` |
| 8 | `H` | `Q` |
| 9 | `I` | `R` |

Example: `00000001940{` (`S9(10)V99`, 12 bytes) → digits `000000019400`, `{` = `0`
positive → `194.00`. `0000005047G` (`S9(09)V99`, 11 bytes) → `G` = `7` positive →
`504.77`.

### Copybook → field map (relevant fields)

**Daily transaction — `CVTRA06Y` (`DALYTRAN-RECORD`, 350 bytes)** — POSTTRAN input:

| Field | PIC | Type |
|-------|-----|------|
| `DALYTRAN-ID` | `X(16)` | text |
| `DALYTRAN-TYPE-CD` | `X(02)` | text |
| `DALYTRAN-CAT-CD` | `9(04)` | unsigned int |
| `DALYTRAN-SOURCE` | `X(10)` | text |
| `DALYTRAN-DESC` | `X(100)` | text |
| `DALYTRAN-AMT` | `S9(09)V99` | signed money |
| `DALYTRAN-MERCHANT-ID` | `9(09)` | unsigned int |
| `DALYTRAN-MERCHANT-NAME/CITY/ZIP` | `X(50)/X(50)/X(10)` | text |
| `DALYTRAN-CARD-NUM` | `X(16)` | text |
| `DALYTRAN-ORIG-TS` / `DALYTRAN-PROC-TS` | `X(26)` | timestamp text |

**Transaction — `CVTRA05Y` (`TRAN-RECORD`, 350 bytes)** — same field set as
`DALYTRAN-RECORD` renamed `TRAN-*`. This is the posted-transaction master.

**Account — `CVACT01Y` (`ACCOUNT-RECORD`, 300 bytes)**:

| Field | PIC |
|-------|-----|
| `ACCT-ID` | `9(11)` |
| `ACCT-ACTIVE-STATUS` | `X(01)` |
| `ACCT-CURR-BAL` | `S9(10)V99` |
| `ACCT-CREDIT-LIMIT` | `S9(10)V99` |
| `ACCT-CASH-CREDIT-LIMIT` | `S9(10)V99` |
| `ACCT-OPEN-DATE` / `ACCT-EXPIRAION-DATE` / `ACCT-REISSUE-DATE` | `X(10)` |
| `ACCT-CURR-CYC-CREDIT` | `S9(10)V99` |
| `ACCT-CURR-CYC-DEBIT` | `S9(10)V99` |
| `ACCT-ADDR-ZIP` | `X(10)` |
| `ACCT-GROUP-ID` | `X(10)` |

**Card cross-reference — `CVACT03Y` (`CARD-XREF-RECORD`, 50 bytes)**:
`XREF-CARD-NUM X(16)`, `XREF-CUST-ID 9(09)`, `XREF-ACCT-ID 9(11)`.

**Transaction category balance — `CVTRA01Y` (`TRAN-CAT-BAL-RECORD`, 50 bytes)**:
key = `TRANCAT-ACCT-ID 9(11)` + `TRANCAT-TYPE-CD X(02)` + `TRANCAT-CD 9(04)`;
value `TRAN-CAT-BAL S9(09)V99`.

**Disclosure group — `CVTRA02Y` (`DIS-GROUP-RECORD`, 50 bytes)**:
key = `DIS-ACCT-GROUP-ID X(10)` + `DIS-TRAN-TYPE-CD X(02)` + `DIS-TRAN-CAT-CD 9(04)`;
value `DIS-INT-RATE S9(04)V99` (annual % rate).

**Customer — `CVCUS01Y`/`CUSTREC` (`CUSTOMER-RECORD`, 500 bytes)**: `CUST-ID`, names,
address lines, `CUST-FICO-CREDIT-SCORE 9(03)`, etc.

**Transaction type — `CVTRA03Y`**: `TRAN-TYPE X(02)`, `TRAN-TYPE-DESC X(50)`.
**Transaction category type — `CVTRA04Y`**: key `TRAN-TYPE-CD X(02)` + `TRAN-CAT-CD 9(04)`, `TRAN-CAT-TYPE-DESC X(50)`.

---

## 2. POSTTRAN — `CBTRN02C` (transaction posting)

Reads the daily transaction file **sequentially**; for every record increments the
transaction counter and runs validation, then either posts or rejects.

### 2.1 Validation (`1500-VALIDATE-TRAN`)

Executed in order; the **first failing group short-circuits** the remaining checks,
except that within the account lookup both checks run and the *later* one wins the
reason code.

1. **Card cross-reference lookup** (`1500-A-LOOKUP-XREF`): read XREF by
   `DALYTRAN-CARD-NUM`.
   - Not found → reject, reason **100** `INVALID CARD NUMBER FOUND`. (Account not checked.)
2. **Account lookup** (`1500-B-LOOKUP-ACCT`, only if step 1 passed): read ACCOUNT by
   `XREF-ACCT-ID`.
   - Not found → reject, reason **101** `ACCOUNT RECORD NOT FOUND`.
   - If found, compute
     `WS-TEMP-BAL = ACCT-CURR-CYC-CREDIT − ACCT-CURR-CYC-DEBIT + DALYTRAN-AMT`.
     - **Credit-limit check**: if `ACCT-CREDIT-LIMIT ≥ WS-TEMP-BAL` → ok,
       else reason **102** `OVERLIMIT TRANSACTION`.
     - **Expiry check** (runs regardless of the credit-limit result): if
       `ACCT-EXPIRAION-DATE ≥ DALYTRAN-ORIG-TS(1:10)` (string compare of `YYYY-MM-DD`)
       → ok, else reason **103** `TRANSACTION RECEIVED AFTER ACCT EXPIRATION`.
     - Because both assignments run sequentially, if **both** fail the stored reason is
       **103** (expiry overwrites over-limit).

A transaction is posted only when the final reason code is `0`.

### 2.2 Posting (`2000-POST-TRANSACTION`)

Performed only for valid transactions, in this order:

1. **Build transaction record**: copy all `DALYTRAN-*` business fields into `TRAN-*`;
   `TRAN-ORIG-TS = DALYTRAN-ORIG-TS`; `TRAN-PROC-TS` = current processing timestamp
   (DB2 `YYYY-MM-DD-HH.MM.SS.mmmmmm` format).
2. **Update transaction-category balance** (`2700-UPDATE-TCATBAL`): key
   `(XREF-ACCT-ID, DALYTRAN-TYPE-CD, DALYTRAN-CAT-CD)`.
   - If the balance record does not exist → **create** it with
     `TRAN-CAT-BAL = DALYTRAN-AMT`.
   - Otherwise → **add** `DALYTRAN-AMT` to the existing `TRAN-CAT-BAL`.
3. **Update account** (`2800-UPDATE-ACCOUNT-REC`):
   - `ACCT-CURR-BAL += DALYTRAN-AMT`.
   - If `DALYTRAN-AMT ≥ 0` → `ACCT-CURR-CYC-CREDIT += DALYTRAN-AMT`,
     else → `ACCT-CURR-CYC-DEBIT += DALYTRAN-AMT`.
4. **Write transaction** to the transaction master.

### 2.3 Reject handling (`2500-WRITE-REJECT-REC`)

For a failed transaction, write a reject record consisting of the original 350-byte
daily transaction data plus an 80-byte validation trailer:
`reason code 9(04)` + `reason description X(76)`. The reject counter is incremented.

### 2.4 Run outcome

Prints processed / rejected counts. If `WS-REJECT-COUNT > 0` the program sets
`RETURN-CODE = 4` (a non-fatal warning; the job still completes).

---

## 3. INTCALC — `CBACT04C` (interest calculation)

Reads the transaction-category balance file **sequentially in key order**
(`acct-id, type-cd, cat-cd`), so all rows for one account are contiguous. Receives a
`PARM-DATE` (`X(10)`, e.g. `2022071800`) used to build generated transaction ids.

### 3.1 Per-account grouping

- On the **first row of a new account** (`TRANCAT-ACCT-ID` changes):
  - If not the very first account overall, `PERFORM 1050-UPDATE-ACCOUNT` for the
    *previous* account.
  - Reset `WS-TOTAL-INT = 0`, remember the new account id, read the ACCOUNT record
    (`1100`) and the XREF record by account id (`1110`, via the alternate index).
- After the last row (EOF) `1050-UPDATE-ACCOUNT` runs once more for the final account.

### 3.2 Per-category interest (`1200`–`1300`)

For every balance row:

1. **Interest rate lookup** (`1200-GET-INTEREST-RATE`): read DISCGRP by
   `(ACCT-GROUP-ID, TRANCAT-TYPE-CD, TRANCAT-CD)`.
   - If not found, retry with `DIS-ACCT-GROUP-ID = 'DEFAULT'` and re-read
     (`1200-A-GET-DEFAULT-INT-RATE`).
2. **Only if `DIS-INT-RATE ≠ 0`**:
   - **Monthly interest** (`1300-COMPUTE-INTEREST`):
     `WS-MONTHLY-INT = (TRAN-CAT-BAL × DIS-INT-RATE) / 1200`
     (annual % → monthly fraction; divide by 100 for percent and by 12 for months).
   - Accumulate `WS-TOTAL-INT += WS-MONTHLY-INT`.
   - **Write a system-generated interest transaction** (`1300-B-WRITE-TX`) to the
     SYSTRAN output with:
     - `TRAN-ID = PARM-DATE || WS-TRANID-SUFFIX` (a 6-digit incrementing suffix
       across the whole run).
     - `TRAN-TYPE-CD = '01'`, `TRAN-CAT-CD = '05'`, `TRAN-SOURCE = 'System'`.
     - `TRAN-DESC = 'Int. for a/c ' || ACCT-ID`.
     - `TRAN-AMT = WS-MONTHLY-INT`, merchant fields blank / `0`.
     - `TRAN-CARD-NUM = XREF-CARD-NUM`; `TRAN-ORIG-TS = TRAN-PROC-TS =` now.
   - `1400-COMPUTE-FEES` is a stub (`To be implemented`) — no effect.

### 3.3 Account update (`1050-UPDATE-ACCOUNT`)

- `ACCT-CURR-BAL += WS-TOTAL-INT`.
- `ACCT-CURR-CYC-CREDIT = 0` and `ACCT-CURR-CYC-DEBIT = 0` (cycle counters reset).
- Rewrite the account record.

---

## 4. COMBTRAN — `SORT` (combine transaction files)

`app/jcl/COMBTRAN.jcl`: a `SORT` step concatenates the previous transaction-master
backup (`TRANSACT.BKUP(0)`) and the system-generated interest transactions
(`SYSTRAN(0)`), sorts ascending by `TRAN-ID` (`SORT FIELDS=(TRAN-ID,A)`), and a
following `IDCAMS REPRO` loads the combined, ordered result back into the transaction
master VSAM. Net effect: **merge posted + interest transactions into one master ordered
by transaction id.**

---

## 5. CREASTMT — `CBSTM03A` (statement generation)

For every card in the XREF file, produces a per-account statement in **two formats:
plain text and HTML**.

Processing:

1. Load all transactions (from the statement transaction file, keyed by card number)
   into an in-memory table grouped by card.
2. For each XREF record: read the CUSTOMER (`2000`, by `XREF-CUST-ID`) and ACCOUNT
   (`3000`, by `XREF-ACCT-ID`).
3. `5000-CREATE-STATEMENT` writes the header block:
   - Customer name (`first middle last`), address lines 1–3 (line 3 = addr3 + state +
     country + zip).
   - **Basic details**: `Account ID`, `Current Balance` (`ACCT-CURR-BAL`),
     `FICO Score` (`CUST-FICO-CREDIT-SCORE`).
4. `4000-TRNXFILE-GET` lists that card's transactions (`Tran ID`, `Tran Details` =
   description, `Tran Amount`) and accumulates `WS-TOTAL-AMT`, then prints
   `Total EXP:` = sum of the listed transaction amounts.
5. Text output is bounded by `START OF STATEMENT` / `END OF STATEMENT` banners; HTML
   output is a styled table (`Bank of XYZ` letterhead, basic details, transaction
   rows, `End of Statement`).

---

## 6. TRANREPT — `CBTRN03C` (transaction detail report)

Reads the (date-filtered, card-sorted) transaction file plus a `DATEPARM` record with a
start/end date. Only transactions whose `TRAN-PROC-TS(1:10)` is within
`[start, end]` are reported.

- On each **new card number**, write the previous card's **Account Total** line.
- For each transaction, resolve `TRAN-TYPE-DESC` (from transaction type) and
  `TRAN-CAT-TYPE-DESC` (from transaction category type) and write a detail line
  (`Tran ID`, `Account ID`, `Type`, `Category`, `Source`, `Amount`).
- Accumulate **page total** (flushed and headers re-emitted every `WS-PAGE-SIZE = 20`
  lines; page totals roll into the grand total) and **account total**.
- At EOF write the final page total and the **Grand Total**.

---

## 7. Orchestration (was JCL chaining + COBSWAIT)

The production run order is defined in `app/scheduler/CardDemo.ca7` (CA7) and
`app/scheduler/CardDemo.controlm` (Control-M). Between jobs the mainframe used
`WAITSTEP` (`PGM=COBSWAIT`, an Assembler/COBOL timer in `app/asm/` waiting a fixed
number of centiseconds) purely to serialise CICS file open/close housekeeping — it
carries **no business logic**.

The core business pipeline, with the timer/housekeeping stripped out, is:

```
POSTTRAN (CBTRN02C) → INTCALC (CBACT04C) → COMBTRAN (SORT) → CREASTMT (CBSTM03A) → TRANREPT (CBTRN03C)
```

The modernized system replaces `COBSWAIT`/JCL triggers with **real data
dependencies**: each step starts only when the previous step has completed
successfully (AWS Step Functions `Next`/`Catch`, or the local docker-compose runner),
never a fixed wait.

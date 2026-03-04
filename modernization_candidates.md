# CardDemo - Microservice Extraction Candidates

This document identifies three capabilities within the CardDemo mainframe application that are strong candidates for extraction into standalone microservices. Each candidate is analyzed in terms of its current implementation, why it is suitable for microservice extraction, and a suggested modernization approach.

---

## Candidate 1: Transaction Posting Service

### Current Implementation

**Batch Job:** `POSTTRAN` (`app/jcl/POSTTRAN.jcl`)
**COBOL Program:** `CBTRN02C` (`app/cbl/CBTRN02C.cbl` -- 732 lines)

#### Processing Pipeline

The program implements a sequential batch pipeline that reads daily transactions and posts them to the transaction master:

```
1000-DALYTRAN-OPEN   -- Open 6 files (DALYTRAN, TRANSACT, XREF, ACCTFILE, DALYREJS, TCATBALF)
     |
     v
1000-DALYTRAN-GET    -- Read next daily transaction record (DALYTRAN-RECORD, 350 bytes)
     |
     v
1500-VALIDATE-TRAN   -- Validate transaction:
     |                   1500-A-LOOKUP-XREF: Read XREF by DALYTRAN-CARD-NUM -> get XREF-ACCT-ID
     |                   1500-B-LOOKUP-ACCT: Read ACCTDATA by XREF-ACCT-ID -> validate:
     |                     - Credit limit check: ACCT-CREDIT-LIMIT >= (cycle_credits - cycle_debits + tran_amt)
     |                     - Expiration check:   ACCT-EXPIRAION-DATE >= DALYTRAN-ORIG-TS(1:10)
     |                   Rejection reasons: 100=invalid card, 101=account not found,
     |                                      102=overlimit, 103=expired account
     |
     v
[Valid?] --NO-->  2500-WRITE-REJECT-REC  -- Write to DALYREJS (430 bytes = 350 tran + 80 trailer)
     |
    YES
     |
     v
2000-POST-TRANSACTION:
     |-- Map DALYTRAN-* fields to TRAN-* fields (TRAN-RECORD, copybook CVTRA05Y)
     |-- Z-GET-DB2-FORMAT-TIMESTAMP -> TRAN-PROC-TS (DB2 timestamp format)
     |-- 2700-UPDATE-TCATBAL: Read/create TCATBALF record, ADD DALYTRAN-AMT to TRAN-CAT-BAL
     |-- 2800-UPDATE-ACCOUNT-REC: ADD DALYTRAN-AMT to ACCT-CURR-BAL,
     |     conditionally add to ACCT-CURR-CYC-CREDIT (>=0) or ACCT-CURR-CYC-DEBIT (<0)
     |-- 2900-WRITE-TRANSACTION-FILE: WRITE TRAN-RECORD to TRANSACT.VSAM.KSDS
```

#### Files Accessed

| DD Name | Dataset | Access Mode | Copybook |
|---|---|---|---|
| `DALYTRAN` | `AWS.M2.CARDDEMO.DALYTRAN.PS` | INPUT (sequential read) | `CVTRA06Y` |
| `TRANFILE` | `AWS.M2.CARDDEMO.TRANSACT.VSAM.KSDS` | OUTPUT (write) | `CVTRA05Y` |
| `XREFFILE` | `AWS.M2.CARDDEMO.CARDXREF.VSAM.KSDS` | INPUT (random read by key) | `CVACT03Y` |
| `ACCTFILE` | `AWS.M2.CARDDEMO.ACCTDATA.VSAM.KSDS` | I-O (random read + rewrite) | `CVACT01Y` |
| `DALYREJS` | `AWS.M2.CARDDEMO.DALYREJS(+1)` | OUTPUT (sequential write) | -- (430-byte composite) |
| `TCATBALF` | `AWS.M2.CARDDEMO.TCATBALF.VSAM.KSDS` | I-O (random read + rewrite/write) | `CVTRA01Y` |

#### Key Source Code Details

- **Validation logic** (lines 380-421): Uses `INVALID KEY` clause on keyed READ operations to detect missing cross-reference or account records. Credit limit validation computes a temporary balance including the pending transaction amount.
- **Account balance update** (lines 545-560): Directly modifies `ACCT-CURR-BAL` and either `ACCT-CURR-CYC-CREDIT` or `ACCT-CURR-CYC-DEBIT` based on transaction sign, then issues `REWRITE`.
- **Category balance maintenance** (lines 467-542): Creates new `TRAN-CAT-BAL-RECORD` if none exists for the account+type+category combination, otherwise updates existing record via `REWRITE`.
- **Error handling** (lines 707-727): Uses `CEE3ABD` (LE runtime abend) for fatal I/O errors. Displays file status codes via `9910-DISPLAY-IO-STATUS` with proper handling of non-numeric status bytes.
- **Return code**: Sets RC=4 via `WS-RETURN-CODE` if any transactions were rejected, RC=0 if all posted successfully.

### Why a Good Microservice Candidate

1. **Clear bounded context**: The program has a well-defined input (daily transaction file), processing logic (validate → post → update balances), and output (transaction master + rejects). This maps directly to a single-responsibility microservice.

2. **No CICS dependency**: `CBTRN02C` is a pure batch program with no `EXEC CICS` commands. It uses standard COBOL file I/O (`OPEN`, `READ`, `WRITE`, `REWRITE`, `CLOSE`), making it simpler to extract than online programs that rely on CICS terminal management.

3. **High business value and change frequency**: Transaction posting is the most critical daily batch operation. It touches the most data stores (6 files) and has the most complex business logic (4 validation rules, 3 update operations). Changes to posting rules, validation criteria, or balance calculations would be the most common type of business-driven change.

4. **Natural streaming boundary**: The sequential read of `DALYTRAN.PS` (one record at a time, process, write results) is architecturally equivalent to consuming messages from a queue or stream. The daily file already acts as a natural event boundary.

5. **Self-contained data transformations**: The field-by-field mapping from `DALYTRAN-*` to `TRAN-*` (lines 425-438) and the timestamp formatting (`Z-GET-DB2-FORMAT-TIMESTAMP`) are isolated transformations with no external dependencies.

### Suggested Modernization Approach

| Aspect | Current State | Target State |
|---|---|---|
| **Input** | Sequential file `DALYTRAN.PS` (350-byte fixed records) | Event stream (Amazon SQS, Apache Kafka, or Amazon Kinesis). Each transaction becomes a message/event. |
| **Processing** | Batch COBOL (`CBTRN02C`) running once daily | Streaming consumer service processing events in near-real-time. REST/gRPC API for synchronous posting. |
| **Validation** | Inline COBOL paragraphs with `INVALID KEY` | Domain service with validation rules engine. Card/account lookups via database queries or cached lookups. |
| **Data Store** | 4 VSAM KSDS files (TRANSACT, ACCTDATA, CARDXREF, TCATBALF) | Relational database (Amazon Aurora, PostgreSQL). Tables: `transactions`, `accounts`, `card_xref`, `category_balances`. |
| **Rejects** | GDG sequential file (`DALYREJS`) | Dead-letter queue (SQS DLQ) or rejects table with structured reason codes. |
| **Scheduling** | Control-M daily batch | Event-driven (continuous) or scheduled via Amazon EventBridge for batch compatibility during transition. |
| **Observability** | `DISPLAY` statements, file status codes | Structured logging, metrics (transaction counts, rejection rates), distributed tracing. |

**Migration Path:**
1. **Phase 1 - Lift**: Recompile COBOL to run on AWS M2 (already supported). Validate functional equivalence.
2. **Phase 2 - Wrap**: Expose the posting logic as a REST API. Replace file input with an API endpoint that accepts transaction JSON. Keep VSAM backend initially.
3. **Phase 3 - Replace**: Rewrite validation and posting logic in Java/Python/Go. Migrate VSAM data to relational database. Replace daily batch with event-driven processing.
4. **Phase 4 - Optimize**: Add real-time posting, eliminate batch window, implement event sourcing for auditability.

---

## Candidate 2: Credit Card Authorization Service

### Current Implementation

**Online CICS Transaction:** `CP00` -- Program `COPAUA0C` (MQ-triggered)
**Authorization View:** `CPVS` (`COPAUS0C`) and `CPVD` (`COPAUS1C`)
**Fraud Handling:** `COPAUS2C` (DB2 insert)
**Batch Purge:** `CBPAUP0J` / `CBPAUP0C`

#### Architecture

The authorization module is the most architecturally advanced component in CardDemo. It already implements a message-driven, multi-data-store pattern:

```
POS Emulator (external)
     |
     | CSV message (18 fields, copybook CCPAURQY)
     v
MQ Queue: AWS.M2.CARDDEMO.PAUTH.REQUEST
     |
     v
CP00 (COPAUA0C) -- MQ-triggered CICS program
     |
     |-- READ CARDXREF.VSAM.KSDS (validate card number)
     |-- Apply business rules:
     |     - Card exists in cross-reference?
     |     - Account active and not expired?
     |     - Transaction amount within credit limit?
     |     - Card not flagged for fraud?
     |
     |-- INSERT/UPDATE IMS DB DBPAUTP0:
     |     - PAUTSUM0 (root segment): Authorization summary
     |     - PAUTDTL1 (child segment): Authorization details
     |
     |-- Write CSV response (6 fields, copybook CCPAURLY)
     v
MQ Queue: AWS.M2.CARDDEMO.PAUTH.REPLY
     |
     v
POS Emulator receives response
```

#### Data Stores

| Store | Type | Access | Purpose |
|---|---|---|---|
| `PAUTH.REQUEST` | MQ Queue | GET (input) | Authorization request messages (CSV, 18 fields) |
| `PAUTH.REPLY` | MQ Queue | PUT (output) | Authorization response messages (CSV, 6 fields) |
| `DBPAUTP0` | IMS DB (HIDAM) | GU/GN/ISRT/REPL (DL/I calls) | Authorization storage. Root: `PAUTSUM0`. Child: `PAUTDTL1`. |
| `DBPAUTX0` | IMS DB Index | -- | HIDAM index for `DBPAUTP0` |
| `AUTHFRDS` | DB2 Table | INSERT | Fraud tracking (27 columns). `PF5` from `COPAUS1C` triggers insert via `COPAUS2C`. |
| `CARDXREF.VSAM.KSDS` | VSAM KSDS | READ | Card-to-account cross-reference for validation |
| `ACCTDATA.VSAM.KSDS` | VSAM KSDS | READ/REWRITE | Account data (for purge job: adjust available credit) |

#### IMS DB Structure

```
DBD: DBPAUTP0 (HIDAM)
  |
  +-- PAUTSUM0 (Root Segment)
  |     Authorization Summary
  |     Key: Card Number + Authorization Timestamp
  |     Fields: card_num, auth_date, auth_time, auth_type,
  |             auth_status, total_amount, approved_count, denied_count
  |
  +-- PAUTDTL1 (Child Segment)
        Authorization Details
        Key: Sequential within parent
        Fields: transaction_id, merchant_id, merchant_name,
                transaction_amount, auth_response_code, auth_reason
```

#### MQ Message Formats

**Request** (copybook `CCPAURQY`, CSV with 18 fields):
```
AUTH-DATE, AUTH-TIME, CARD-NUM, AUTH-TYPE, CARD-EXPIRY-DATE,
MESSAGE-TYPE, MESSAGE-SOURCE, PROCESSING-CODE, TRANSACTION-AMT,
MERCHANT-CATAGORY-CODE, ACQR-COUNTRY-CODE, POS-ENTRY-MODE,
MERCHANT-ID, MERCHANT-NAME, MERCHANT-CITY, MERCHANT-STATE,
MERCHANT-ZIP, TRANSACTION-ID
```

**Reply** (copybook `CCPAURLY`, CSV with 6 fields):
```
CARD-NUM, TRANSACTION-ID, AUTH-ID-CODE, AUTH-RESP-CODE,
AUTH-RESP-REASON, APPROVED-AMT
```

#### Batch Purge Job

`CBPAUP0C` runs on a schedule to remove expired authorizations from IMS DB. For each expired authorization:
1. Read summary segment (`PAUTSUM0`) via DL/I `GN` call
2. Check expiration criteria
3. Delete detail segments (`PAUTDTL1`) via DL/I `DLET` call
4. Delete summary segment
5. Rewrite account record to adjust available credit in `ACCTDATA.VSAM.KSDS`

### Why a Good Microservice Candidate

1. **Pre-existing microservice boundary**: The MQ request/reply pattern already defines a clean service interface. The authorization module communicates with the outside world exclusively through message queues, not through shared data or program control flow. This is the textbook definition of a service boundary.

2. **Completely self-contained data stores**: The module owns its own dedicated data stores (IMS DB `DBPAUTP0` for authorization data, DB2 `AUTHFRDS` for fraud tracking) that are not shared with any other CardDemo module. No other program reads from or writes to these stores.

3. **Real-time latency requirements**: Authorization decisions must happen in real-time (while the cardholder is at the point of sale). This makes it fundamentally different from the batch-oriented rest of the application and naturally suits a low-latency microservice deployment.

4. **Independent scaling**: Authorization volume is driven by external POS traffic, which has different scaling characteristics than internal batch processing. As a standalone service, it can be independently scaled based on incoming request volume.

5. **Technology isolation**: The module is the only part of CardDemo that uses IMS DB and DB2. Extracting it removes the dependency on these complex mainframe subsystems from the rest of the application.

### Suggested Modernization Approach

| Aspect | Current State | Target State |
|---|---|---|
| **Interface** | MQ request/reply queues (CSV format) | REST/gRPC API with JSON payloads. Async option via Amazon SQS or EventBridge. |
| **Authorization Logic** | COBOL program `COPAUA0C` in CICS | Java/Go/Python microservice with business rules engine. Card validation via cached lookups. |
| **Authorization Storage** | IMS DB HIDAM (`DBPAUTP0`, 2 segment types) | Amazon DynamoDB (document store) or PostgreSQL. DynamoDB natural fit: partition key=card_num, sort key=auth_timestamp. |
| **Fraud Tracking** | DB2 table `AUTHFRDS` (27 columns) | PostgreSQL table or dedicated fraud detection service. Integration with Amazon Fraud Detector for ML-based detection. |
| **Purge/Housekeeping** | Batch job `CBPAUP0C` with DL/I calls | TTL-based expiration (DynamoDB TTL) or scheduled Lambda function. |
| **Viewing UI** | CICS screens `CPVS`/`CPVD` (BMS maps) | Web UI or admin API. Dashboard for authorization monitoring. |

**Migration Path:**
1. **Phase 1 - Decouple**: Keep MQ interface but route to a new service. Implement the authorization logic in the target language, reading from and writing to a modern database.
2. **Phase 2 - Migrate Data**: Export IMS DB authorization data to DynamoDB/PostgreSQL. Map HIDAM segments to tables/documents. Migrate DB2 fraud data.
3. **Phase 3 - Replace Interface**: Replace MQ with REST/gRPC API. Update POS integration to call the new API directly.
4. **Phase 4 - Enhance**: Add ML-based fraud detection, real-time authorization analytics, and configurable business rules.

---

## Candidate 3: User Management Service

### Current Implementation

**CICS Transactions:** `CU00`, `CU01`, `CU02`, `CU03`
**COBOL Programs:** `COUSR00C` (list), `COUSR01C` (add), `COUSR02C` (update), `COUSR03C` (delete)
**Initialization Batch Job:** `DUSRSECJ` (`app/jcl/DUSRSECJ.jcl`)

#### CRUD Operations

The four programs implement a complete CRUD lifecycle on the `USRSEC` VSAM KSDS file:

**List Users (`CU00` / `COUSR00C` -- 696 lines):**
- Paginated display of 10 users per page using `EXEC CICS STARTBR`, `READNEXT`, `READPREV`, `ENDBR`
- Forward pagination (`PF8`): `READNEXT` loop, stores last user ID for next page
- Backward pagination (`PF7`): `READPREV` loop, stores first user ID for previous page
- Selection: type `U` next to a user to update (transfers to `COUSR02C`), `D` to delete (transfers to `COUSR03C`)
- Filter: optional starting user ID filter via `USRIDINI` input field
- Tracks state in COMMAREA: `CDEMO-CU00-USRID-FIRST`, `CDEMO-CU00-USRID-LAST`, `CDEMO-CU00-PAGE-NUM`, `CDEMO-CU00-NEXT-PAGE-FLG`

**Add User (`CU01` / `COUSR01C` -- 300 lines):**
- Field validation: First name, last name, user ID, password, and user type must all be non-empty
- Maps screen fields to copybook fields: `USERIDI` → `SEC-USR-ID`, `FNAMEI` → `SEC-USR-FNAME`, etc.
- Writes via `EXEC CICS WRITE DATASET('USRSEC')` with `RIDFLD(SEC-USR-ID)` and `KEYLENGTH(LENGTH OF SEC-USR-ID)`
- Handles duplicate key (`DFHRESP(DUPKEY)` / `DFHRESP(DUPREC)`) with user-friendly error message
- `PF4` clears the form

**Update User (`CU02` / `COUSR02C`):**
- Reads existing record via `EXEC CICS READ ... UPDATE`
- Displays current values, allows modification
- Commits changes via `EXEC CICS REWRITE`

**Delete User (`CU03` / `COUSR03C`):**
- Reads existing record, displays for confirmation
- On confirmation, deletes via `EXEC CICS DELETE`

#### Data Store

| Dataset | Copybook | Record Length | Key | Key Length |
|---|---|---|---|---|
| `AWS.M2.CARDDEMO.USRSEC.VSAM.KSDS` | `CSUSR01Y` | 80 bytes | `SEC-USR-ID` | 8 bytes |

**Record Layout** (`CSUSR01Y`):
```cobol
01 SEC-USER-DATA.
    05 SEC-USR-ID                 PIC X(08).    -- User ID (primary key)
    05 SEC-USR-FNAME              PIC X(20).    -- First name
    05 SEC-USR-LNAME              PIC X(20).    -- Last name
    05 SEC-USR-PWD                PIC X(08).    -- Password (plaintext)
    05 SEC-USR-TYPE               PIC X(01).    -- 'A' = Admin, 'U' = Regular user
    05 SEC-USR-FILLER             PIC X(23).    -- Reserved
```

#### Initialization Job (`DUSRSECJ`)

The JCL job (`app/jcl/DUSRSECJ.jcl`) performs a 3-step initialization:
1. **PREDEL** (`IEFBR14`): Delete existing `USRSEC.PS` file
2. **STEP01** (`IEBGENER`): Create `USRSEC.PS` from in-stream seed data (10 users):
   - 5 admins: `ADMIN001`-`ADMIN005` (type `A`, password `PASSWORD`)
   - 5 users: `USER0001`-`USER0005` (type `U`, password `PASSWORD`)
3. **STEP02** (`IDCAMS`): Define VSAM KSDS cluster with keys(8,0), recordsize(80,80), CISZ(8192)
4. **STEP03** (`IDCAMS`): REPRO from `USRSEC.PS` to `USRSEC.VSAM.KSDS`

#### Authentication Integration

The signon program `COSGN00C` reads from the same `USRSEC` VSAM file:
```cobol
EXEC CICS READ DATASET(WS-USRSEC-FILE) INTO(SEC-USER-DATA)
     RIDFLD(WS-USER-ID) KEYLENGTH(LENGTH OF WS-USER-ID)
```
- Validates password: `SEC-USR-PWD = WS-USER-PWD`
- Routes by type: `CDEMO-USRTYP-ADMIN` → `COADM01C`, else → `COMEN01C`
- Passwords are stored and compared in uppercase plaintext

### Why a Good Microservice Candidate

1. **Complete CRUD on an isolated data store**: The four user management programs (`COUSR00C`-`COUSR03C`) operate exclusively on the `USRSEC` VSAM file. No other CardDemo module writes to this file (except the initialization job and the signon program which only reads). This is the cleanest data boundary in the entire application.

2. **Zero dependency on business data**: User management has no dependency on accounts, cards, transactions, or any other business entity. It is purely an identity/access management function. This means it can be extracted without any ripple effects on business logic.

3. **Standard IAM pattern**: The user record structure (ID, name, password, role) maps directly to modern identity management concepts. The CRUD operations map directly to standard REST API patterns (GET /users, POST /users, PUT /users/{id}, DELETE /users/{id}).

4. **Simple data model**: At 80 bytes with only 5 meaningful fields and a simple 8-byte primary key, the `USRSEC` record is the simplest data structure in CardDemo. Migration to any modern database is trivial.

5. **Security improvement opportunity**: The current implementation stores passwords in plaintext (8 characters, uppercase). Extracting this as a microservice provides a natural opportunity to implement proper password hashing, multi-factor authentication, and integration with cloud identity providers.

6. **Low risk**: Because user management is functionally independent from the core business operations, extracting it carries the lowest risk of any candidate. If the new service has issues, the impact is limited to user administration -- not to transaction processing or account management.

### Suggested Modernization Approach

| Aspect | Current State | Target State |
|---|---|---|
| **Interface** | CICS BMS screens (`COUSR00`-`COUSR03`) | REST API: `GET/POST/PUT/DELETE /api/v1/users`. Admin web UI. |
| **Authentication** | COBOL `COSGN00C` with plaintext password comparison | OAuth 2.0 / OpenID Connect. JWT tokens. Integration with Amazon Cognito or Auth0. |
| **Data Store** | VSAM KSDS (80-byte fixed records, 8-byte key) | Relational database (PostgreSQL/Aurora) or cloud identity provider's built-in user store. |
| **Password Storage** | Plaintext `SEC-USR-PWD` PIC X(08) | bcrypt/scrypt hashed passwords with salt. Password policy enforcement. |
| **User Types** | Single character: `A` (admin) or `U` (user) | Role-based access control (RBAC) with configurable roles and permissions. |
| **Initialization** | JCL job `DUSRSECJ` with `IEBGENER` from in-stream data | Database migration scripts (Flyway/Liquibase) with seed data. |
| **Session Management** | CICS COMMAREA (`CDEMO-USER-ID`, `CDEMO-USER-TYPE`) | JWT tokens with configurable expiration. Session store (Redis/DynamoDB). |

**Migration Path:**
1. **Phase 1 - API Gateway**: Deploy a thin REST API in front of the existing VSAM-backed user management. The API translates HTTP requests to VSAM operations (initially via a COBOL wrapper or direct VSAM access library).
2. **Phase 2 - Database Migration**: Migrate the 80-byte VSAM records to a PostgreSQL `users` table. Implement proper password hashing during migration (prompt all users for password reset).
3. **Phase 3 - Cloud Identity**: Replace custom user management with Amazon Cognito user pools. Map existing user types to Cognito groups. Implement OAuth 2.0 flows.
4. **Phase 4 - Decommission**: Remove CICS user management transactions (`CU00`-`CU03`). Update signon (`COSGN00C`) to authenticate against the new identity provider via API call instead of VSAM read. Eventually replace `COSGN00C` with a web-based login page.

**Database Schema (Phase 2):**
```sql
CREATE TABLE users (
    user_id       VARCHAR(8)   PRIMARY KEY,  -- maps to SEC-USR-ID
    first_name    VARCHAR(20)  NOT NULL,     -- maps to SEC-USR-FNAME
    last_name     VARCHAR(20)  NOT NULL,     -- maps to SEC-USR-LNAME
    password_hash VARCHAR(255) NOT NULL,     -- replaces SEC-USR-PWD (plaintext)
    user_type     VARCHAR(1)   NOT NULL      -- maps to SEC-USR-TYPE
                  CHECK (user_type IN ('A', 'U')),
    created_at    TIMESTAMP    DEFAULT NOW(),
    updated_at    TIMESTAMP    DEFAULT NOW()
);

-- Seed data (passwords would be hashed in practice)
INSERT INTO users (user_id, first_name, last_name, password_hash, user_type)
VALUES
    ('ADMIN001', 'MARGARET', 'GOLD', '$2b$12$...', 'A'),
    ('USER0001', 'LAWRENCE', 'THOMAS', '$2b$12$...', 'U');
```

---

## Comparison Matrix

| Criterion | Transaction Posting | Authorization | User Management |
|---|---|---|---|
| **Extraction Complexity** | Medium | High | Low |
| **Business Risk** | High (core daily process) | Medium (optional module) | Low (independent function) |
| **Data Store Migration** | 4 VSAM files → RDBMS | IMS DB + DB2 → DynamoDB/RDBMS | 1 VSAM file → RDBMS or Cognito |
| **Interface Change** | File → Stream/API | MQ → REST/gRPC | BMS screens → REST API |
| **Lines of Code** | ~730 (1 program) | ~2,000+ (5 programs) | ~1,600 (4 programs) |
| **External Dependencies** | None | MQ, IMS DB, DB2 | None |
| **Recommended Priority** | 2nd | 3rd | 1st (quick win) |
| **Estimated Effort** | 2-3 sprints | 4-6 sprints | 1-2 sprints |

### Recommended Extraction Order

1. **User Management** (quick win): Lowest risk, simplest data model, immediate security improvements. Demonstrates the extraction pattern for the team.
2. **Transaction Posting** (high value): Highest business impact. Enables real-time transaction processing. More complex but well-bounded.
3. **Authorization** (most complex): Already has the cleanest service boundary but involves the most technologies (MQ, IMS DB, DB2). Best tackled last when the team has experience from the first two extractions.

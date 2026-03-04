# CardDemo - Mainframe Architecture Documentation

## 1. Executive Summary

CardDemo is a comprehensive IBM z/OS mainframe application simulating a credit card management system. It is built on **COBOL/CICS/JCL** with **VSAM KSDS** as the primary data store and includes optional extensions for **IMS DB**, **DB2**, and **MQ**. The application serves as a realistic modernization target for AWS and partner tooling evaluation.

The system is split into two processing layers:

- **Online (CICS)** -- Interactive terminal transactions for account management, card operations, transaction entry, billing, reporting, and user administration.
- **Batch (JCL)** -- Scheduled jobs orchestrated via Control-M for daily transaction posting, monthly interest calculation, statement generation, and data maintenance.

---

## 2. Main Business Capabilities

| # | Capability | Description | Key Programs | Data Stores |
|---|---|---|---|---|
| 1 | **Authentication & Security** | User signon with userid/password validation against VSAM. Role-based routing: admin users (`SEC-USR-TYPE = 'A'`) go to admin menu (`COADM01C`), regular users (`SEC-USR-TYPE = 'U'`) go to main menu (`COMEN01C`). User CRUD operations (list/add/update/delete). | `COSGN00C`, `COUSR00C`-`COUSR03C` | `USRSEC.VSAM.KSDS` (80-byte records, key: `SEC-USR-ID` PIC X(08)) |
| 2 | **Account Management** | View and update account information including current balance, credit limit, cash credit limit, open/expiration/reissue dates, cycle credits/debits, and group ID. | `COACTVWC`, `COACTUPC` | `ACCTDATA.VSAM.KSDS` (300-byte records, key: `ACCT-ID` PIC 9(11)) |
| 3 | **Credit Card Management** | List, view, and update credit cards. Cross-reference cards to accounts and customers. Card records include card number, account ID, CVV, embossed name, expiration date, and active status. | `COCRDLIC`, `COCRDSLC`, `COCRDUPC` | `CARDDATA.VSAM.KSDS` (150 bytes), `CARDXREF.VSAM.KSDS` (50 bytes) |
| 4 | **Transaction Processing** | Add, view, list transactions online. Daily batch posting validates card via XREF lookup, checks credit limits and account expiration, updates account balances and category balances, writes to transaction master. Rejected transactions written to GDG with reason codes (100=invalid card, 101=account not found, 102=overlimit, 103=expired account). On-demand transaction reporting via `TRANREPT` batch submission from CICS. | `COTRN00C`-`COTRN02C` (online), `CBTRN02C` (batch posting), `CBTRN03C` (reporting) | `TRANSACT.VSAM.KSDS` (350 bytes), `DALYTRAN.PS` (350 bytes), `TCATBALF.VSAM.KSDS` (50 bytes), `DALYREJS` GDG (430 bytes) |
| 5 | **Billing & Statements** | Bill payment via CICS. Monthly interest calculation reads transaction category balances, looks up disclosure group interest rates (with DEFAULT fallback), computes `monthly_interest = (balance * rate) / 1200`, updates account balances, and writes interest transactions. Statement generation produces both plain text (`.PS`) and HTML (`.HTML`) output using a subroutine (`CBSTM03B`) for all file I/O. Demonstrates mainframe control block addressing, ALTER/GO TO, COMP/COMP-3, 2D arrays, and CALL to subroutine. | `COBIL00C` (online), `CBACT04C` (interest), `CBSTM03A`/`CBSTM03B` (statements) | `ACCTDATA`, `TCATBALF`, `DISCGRP`, `CARDXREF`, `CUSTDATA`, `TRANSACT` |
| 6 | **Authorization (Optional)** | Real-time MQ-based credit card authorization. POS emulator sends CSV authorization requests via MQ. CICS program processes requests, validates against VSAM cross-reference data, applies business rules, stores authorization details in IMS DB (HIDAM), sends responses via reply queue. Fraud detection marks suspicious transactions and stores in DB2 `AUTHFRDS` table. Batch purge of expired authorizations adjusts available credit. | `COPAUA0C` (MQ trigger), `COPAUS0C`/`COPAUS1C` (view), `COPAUS2C` (fraud/DB2), `CBPAUP0C` (batch purge) | IMS DB `DBPAUTP0`, DB2 `AUTHFRDS`, MQ queues |

### Additional Capabilities

| Capability | Description | Key Programs |
|---|---|---|
| **Transaction Type Management (Optional DB2)** | Maintain transaction type reference data in DB2 tables. Add, update, delete transaction types from CICS. Demonstrates DB2 cursors and SQL operations. | `COTRTUPC` (add/edit), `COTRTLIC` (list/update/delete), `COBTUPDT` (batch maintain) |
| **MQ Account Extractions (Optional)** | System date inquiry (`CDRD`/`CODATE01`) and account details inquiry (`CDRA`/`COACCT01`) via MQ request/response pattern. | `CODATE01`, `COACCT01` |
| **Data Export/Import** | Branch migration pipeline. `CBEXPORT` reads 5 master VSAM files and writes a single consolidated 500-byte file with type discriminator (`C`/`A`/`X`/`T`/`D`). `CBIMPORT` fans records back out. | `CBEXPORT`, `CBIMPORT` |

---

## 3. Architecture Map

### 3.1 Online CICS Programs

All online programs share the `CARDDEMO-COMMAREA` (copybook `COCOM01Y`) for inter-program communication via `EXEC CICS XCTL`. The COMMAREA carries user ID, user type (Admin/User), source/target transaction IDs, program names, customer/account/card context, and last map/mapset info.

| Transaction | BMS Map | Program | Function | Optional Module | VSAM Files Accessed | Notes |
|---|---|---|---|---|---|---|
| `CC00` | `COSGN00` | `COSGN00C` | Signon Screen | -- | `USRSEC` (READ) | Entry point. Routes admin to `COADM01C`, users to `COMEN01C`. Password validated via `SEC-USR-PWD`. |
| `CM00` | `COMEN01` | `COMEN01C` | Main Menu | -- | -- | Navigation hub for regular users. PF-key driven menu. |
| `CAVW` | `COACTVW` | `COACTVWC` | Account View | -- | `ACCTDATA` (READ), `CARDXREF` (READ) | Read-only account display. |
| `CAUP` | `COACTUP` | `COACTUPC` | Account Update | -- | `ACCTDATA` (READ/REWRITE), `CARDXREF` (READ) | Multi-step: fetch details, show details, confirm changes, commit. Uses `ACUP-CHANGE-ACTION` flag. |
| `CCLI` | `COCRDLI` | `COCRDLIC` | Credit Card List | -- | `CARDDATA` (BROWSE), `CARDXREF` (READ) | Paginated list with PF7/PF8 scrolling. |
| `CCDL` | `COCRDSL` | `COCRDSLC` | Credit Card View | -- | `CARDDATA` (READ), `CARDXREF` (READ) | Read-only card detail display. |
| `CCUP` | `COCRDUP` | `COCRDUPC` | Credit Card Update | -- | `CARDDATA` (READ/REWRITE), `CARDXREF` (READ) | Update card attributes. |
| `CT00` | `COTRN00` | `COTRN00C` | Transaction List | -- | `TRANSACT` (BROWSE), `CARDXREF` (READ) | Paginated transaction list. |
| `CT01` | `COTRN01` | `COTRN01C` | Transaction View | -- | `TRANSACT` (READ) | Read-only transaction detail. |
| `CT02` | `COTRN02` | `COTRN02C` | Transaction Add | -- | `TRANSACT` (WRITE), `CARDXREF` (READ), `TRANTYPE` (READ), `TRANCATG` (READ) | Online transaction entry with type/category validation. |
| `CR00` | `CORPT00` | `CORPT00C` | Transaction Reports | -- | -- | Submits `TRANREPT` batch job (program `CBTRN03C`) via internal reader or similar mechanism. |
| `CB00` | `COBIL00` | `COBIL00C` | Bill Payment | -- | `ACCTDATA` (READ/REWRITE), `TRANSACT` (WRITE), `CARDXREF` (READ) | Processes bill payments, updates account balance. |
| `CA00` | `COADM01` | `COADM01C` | Admin Menu | DB2 Tran Type Mgmt | -- | Navigation hub for admin users. Options 5-6 enabled with DB2 module. |
| `CU00` | `COUSR00` | `COUSR00C` | List Users | -- | `USRSEC` (BROWSE) | Paginated user list, 10 per page. Selection: `U`=update, `D`=delete. Uses `STARTBR`/`READNEXT`/`READPREV`/`ENDBR`. |
| `CU01` | `COUSR01` | `COUSR01C` | Add User | -- | `USRSEC` (WRITE) | Validates first name, last name, user ID, password, user type. Checks for duplicate keys. |
| `CU02` | `COUSR02` | `COUSR02C` | Update User | -- | `USRSEC` (READ/REWRITE) | Updates user attributes. |
| `CU03` | `COUSR03` | `COUSR03C` | Delete User | -- | `USRSEC` (READ/DELETE) | Confirms deletion before removing record. |
| `CPVS` | `COPAU00` | `COPAUS0C` | Pending Auth Summary | IMS-DB2-MQ | IMS `DBPAUTP0` (READ), `ACCTDATA` (READ), `CARDXREF` (READ) | *(Optional)* Displays authorization summaries from IMS HIDAM database. |
| `CPVD` | `COPAU01` | `COPAUS1C` | Pending Auth Details | IMS-DB2-MQ | IMS `DBPAUTP0` (READ/UPDATE), DB2 `AUTHFRDS` (INSERT) | *(Optional)* PF5 marks transaction as fraudulent, inserts into DB2. Two-phase commit across IMS and DB2. |
| `CP00` | -- | `COPAUA0C` | Process Auth Requests | IMS-DB2-MQ | MQ queues, IMS `DBPAUTP0` (INSERT/UPDATE), `CARDXREF` (READ) | *(Optional)* MQ-triggered. Reads request from `PAUTH.REQUEST`, processes, writes response to `PAUTH.REPLY`, stores in IMS. |
| `CTTU` | `COTRTUP` | `COTRTUPC` | Tran Type Add/Edit | DB2 Tran Type Mgmt | DB2 `TRANSACTION_TYPE` (INSERT/UPDATE) | *(Optional)* Demonstrates DB2 INSERT and UPDATE from CICS. |
| `CTLI` | `COTRTLI` | `COTRTLIC` | Tran Type List/Delete | DB2 Tran Type Mgmt | DB2 `TRANSACTION_TYPE` (SELECT/DELETE) | *(Optional)* Demonstrates DB2 cursor and DELETE from CICS. |
| `CDRD` | -- | `CODATE01` | System Date Inquiry | MQ Integration | MQ request/response | *(Optional)* Demonstrates MQ request/response pattern for date inquiry. |
| `CDRA` | -- | `COACCT01` | Account Details via MQ | MQ Integration | MQ request/response, `ACCTDATA` (READ) | *(Optional)* Demonstrates MQ request/response pattern for account inquiry. |

### 3.2 Batch Jobs

| Job | Program | Function | Frequency | Input Files | Output Files | Notes |
|---|---|---|---|---|---|---|
| `CLOSEFIL` | `IEFBR14` | Close VSAM files in CICS | Daily (first) | -- | -- | Allows batch exclusive access to VSAM files. |
| `ACCTFILE` | `IDCAMS` | Refresh Account Master | Init | `ACCTDATA.PS` | `ACCTDATA.VSAM.KSDS` | REPRO from sequential to KSDS. |
| `CARDFILE` | `IDCAMS` | Refresh Card Master | Init | `CARDDATA.PS` | `CARDDATA.VSAM.KSDS` | REPRO from sequential to KSDS. |
| `CUSTFILE` | `IDCAMS` | Refresh Customer Master | Init | `CUSTDATA.PS` | `CUSTDATA.VSAM.KSDS` | REPRO from sequential to KSDS. |
| `XREFFILE` | `IDCAMS` | Refresh Cross-Reference | Init | `CARDXREF.PS` | `CARDXREF.VSAM.KSDS` | REPRO from sequential to KSDS. |
| `TRANBKP` | `IDCAMS` | Refresh/Backup Transaction Master | Daily | `DALYTRAN.PS.INIT` | `TRANSACT.VSAM.KSDS` | Also used for backup before daily run. |
| `TRANEXTR` | `DSNTIAUL` | Extract DB2 Transaction Types | Weekly (Optional) | DB2 `TRANSACTION_TYPE` | Sequential files | *(Optional)* Extracts latest DB2 data for VSAM refresh. |
| `TRANCATG` | `IDCAMS` | Load Transaction Categories | Init | `TRANCATG.PS` | `TRANCATG.VSAM.KSDS` | 60-byte records. |
| `TRANTYPE` | `IDCAMS` | Load Transaction Types | Init | `TRANTYPE.PS` | `TRANTYPE.VSAM.KSDS` | 60-byte records. |
| `DISCGRP` | `IDCAMS` | Load Disclosure Groups | Init/Weekly | `DISCGRP.PS` | `DISCGRP.VSAM.KSDS` | 50-byte records. Interest rate lookup. |
| `TCATBALF` | `IDCAMS` | Refresh Tran Category Balance | Init | `TCATBALF.PS` | `TCATBALF.VSAM.KSDS` | 50-byte records. |
| `DUSRSECJ` | `IEBGENER` + `IDCAMS` | Initial Load User Security | Init | In-stream data (10 seed users) | `USRSEC.PS` then `USRSEC.VSAM.KSDS` | 3 steps: delete old PS, create PS from in-stream, DEFINE KSDS + REPRO. Seed data: 5 admins (ADMIN001-005), 5 users (USER0001-0005), all with password `PASSWORD`. |
| `POSTTRAN` | `CBTRN02C` | **Core Transaction Posting** | Daily | `DALYTRAN.PS` (sequential read) | `TRANSACT.VSAM.KSDS` (write), `ACCTDATA.VSAM.KSDS` (I-O rewrite), `TCATBALF.VSAM.KSDS` (I-O rewrite/write), `DALYREJS` GDG (write) | Opens 6 files. For each daily transaction: validates card via XREF, validates account exists, checks credit limit (`ACCT-CREDIT-LIMIT >= cycle_credits - cycle_debits + tran_amt`), checks account not expired. Valid transactions posted to TRANSACT, account balances updated, category balances updated/created. Invalid transactions written to DALYREJS with 80-byte validation trailer. Returns RC=4 if any rejections. |
| `INTCALC` | `CBACT04C` | Monthly Interest Calculation | Monthly | `TCATBALF.VSAM.KSDS` (sequential read), `CARDXREF.VSAM.KSDS` (random read via AIX), `DISCGRP.VSAM.KSDS` (random read), `ACCTDATA.VSAM.KSDS` (random I-O) | `SYSTRAN` GDG (sequential write) | Accepts `PARM='YYYYMMDD00'` date. Iterates transaction category balances grouped by account. For each account: looks up disclosure group interest rate (falls back to `DEFAULT` group), computes `monthly_interest = (balance * rate) / 1200`, writes interest transaction records, updates account balance (`ACCT-CURR-BAL += total_interest`, resets `ACCT-CURR-CYC-CREDIT` and `ACCT-CURR-CYC-DEBIT` to 0). Fee computation (`1400-COMPUTE-FEES`) is stubbed out. |
| `COMBTRAN` | `SORT` | Combine Transaction Files | Monthly | System transactions + daily transactions | Combined sorted file | Merges `SYSTRAN` GDG with `TRANSACT.VSAM.KSDS`. |
| `CREASTMT` | `CBSTM03A` / `CBSTM03B` | Produce Account Statements | Monthly | `TRANSACT.VSAM.KSDS`, `CARDXREF.VSAM.KSDS`, `ACCTDATA.VSAM.KSDS`, `CUSTDATA.VSAM.KSDS` | `STATEMNT.PS` (text), `STATEMNT.HTML` (HTML) | 4-step JCL pipeline: (1) IDCAMS define temp KSDS, (2) SORT transactions by card+tran ID with OUTREC field rearrangement, (3) delete old statement files, (4) run `CBSTM03A`. Statement program demonstrates mainframe control block addressing (PSA->TCB->TIOT), ALTER/GO TO, 2D arrays (51 cards x 10 transactions), and CALL to `CBSTM03B` subroutine for file I/O (operations: O=open, C=close, R=sequential read, K=keyed read). |
| `TRANIDX` | `IDCAMS` | Define AIX for Transaction File | Daily | `TRANSACT.VSAM.KSDS` | AIX + PATH | Alternate index on transaction file for non-primary-key access. |
| `OPENFIL` | `IEFBR14` | Open Files in CICS | Daily (last) | -- | -- | Makes VSAM files available to CICS after batch processing. |
| `WAITSTEP` | `COBSWAIT` | Wait/Synchronization Job | Daily | -- | -- | Assembler program (`MVSWAIT`). Acts as join point in scheduler dependency chain. |
| `TRANREPT` | `CBTRN03C` | Transaction Report | On-demand | `TRANSACT.VSAM.KSDS` | Report output | Submitted from CICS transaction `CR00` (`CORPT00C`). |
| `CBPAUP0J` | `CBPAUP0C` | Purge Expired Authorizations | Optional | IMS `DBPAUTP0` | IMS `DBPAUTP0` (deletes), `ACCTDATA` (rewrite) | *(Optional)* Removes expired authorizations, adjusts available credit. |
| `MNTTRDB2` | `COBTUPDT` | Maintain Transaction Type Table | Weekly (Optional) | Input data | DB2 `TRANSACTION_TYPE` | *(Optional)* Batch DB2 table maintenance. |
| `CBEXPORT` | `CBEXPORT` | Export Data for Migration | On-demand | 5 master VSAM files | `EXPFILE` (500-byte consolidated) | Uses `CVEXPORT.cpy` with `REDEFINES` for each record type (C/A/X/T/D). |
| `CBIMPORT` | `CBIMPORT` | Import Normalized Data | On-demand | `EXPFILE` | 5 separate output files | Reverses the export process. |

### 3.3 Batch Execution Sequences (from Control-M)

**Daily Transaction Backup** (`DAILY-TransactionBackup` folder):
```
CLOSEFIL --> TRANBKP --> WAITSTEP --> OPENFIL
```

**Monthly Interest Calculation** (`MONTHLY-InterestCalculation` folder):
```
CLOSEFIL --> INTCALC --> COMBTRAN --> WAITSTEP --> OPENFIL
```

**Weekly Transaction Types DB Refresh** (`WEEKLY-TransactionTypesDBRefresh`):
```
MNTTRDB2 --> TRANEXTR
```

**Weekly Disclosure Groups Refresh** (`WEEKLY-DisclosureGroupsRefresh`):
Triggered after `MNTTRDB2` completes:
```
CLOSEFIL --> DISCGRP --> WAITSTEP --> OPENFIL
```

**Full Daily Batch Sequence** (as documented in README):
```
CLOSEFIL --> ACCTFILE --> CARDFILE --> XREFFILE --> CUSTFILE --> TRANBKP
--> [TRANEXTR] --> TRANCATG --> TRANTYPE --> DISCGRP --> TCATBALF --> DUSRSECJ
--> POSTTRAN --> INTCALC --> TRANBKP --> COMBTRAN --> CREASTMT --> TRANIDX
--> OPENFIL --> WAITSTEP --> [CBPAUP0J]
```

---

## 4. Data Storage

### 4.1 VSAM KSDS Files (Primary Data Store)

| Dataset | Copybook | Record Length | Key | Key Length | Key Offset | Purpose | Fields |
|---|---|---|---|---|---|---|---|
| `AWS.M2.CARDDEMO.USRSEC.VSAM.KSDS` | `CSUSR01Y` | 80 bytes | `SEC-USR-ID` | 8 | 0 | User security credentials | `SEC-USR-ID` X(08), `SEC-USR-FNAME` X(20), `SEC-USR-LNAME` X(20), `SEC-USR-PWD` X(08), `SEC-USR-TYPE` X(01) ('A'=admin, 'U'=user), FILLER X(23) |
| `AWS.M2.CARDDEMO.ACCTDATA.VSAM.KSDS` | `CVACT01Y` | 300 bytes | `ACCT-ID` | 11 | 0 | Account master records | `ACCT-ID` 9(11), `ACCT-ACTIVE-STATUS` X(01), `ACCT-CURR-BAL` S9(10)V99, `ACCT-CREDIT-LIMIT` S9(10)V99, `ACCT-CASH-CREDIT-LIMIT` S9(10)V99, `ACCT-OPEN-DATE` X(10), `ACCT-EXPIRAION-DATE` X(10), `ACCT-REISSUE-DATE` X(10), `ACCT-CURR-CYC-CREDIT` S9(10)V99, `ACCT-CURR-CYC-DEBIT` S9(10)V99, `ACCT-ADDR-ZIP` X(10), `ACCT-GROUP-ID` X(10), FILLER X(178) |
| `AWS.M2.CARDDEMO.CARDDATA.VSAM.KSDS` | `CVACT02Y` | 150 bytes | `CARD-NUM` | 16 | 0 | Credit card master records | `CARD-NUM` X(16), `CARD-ACCT-ID` 9(11), `CARD-CVV-CD` 9(03), `CARD-EMBOSSED-NAME` X(50), `CARD-EXPIRAION-DATE` X(10), `CARD-ACTIVE-STATUS` X(01), FILLER X(59) |
| `AWS.M2.CARDDEMO.CUSTDATA.VSAM.KSDS` | `CVCUS01Y` | 500 bytes | `CUST-ID` | 9 | 0 | Customer master records | `CUST-ID` 9(09), `CUST-FIRST-NAME` X(25), `CUST-MIDDLE-NAME` X(25), `CUST-LAST-NAME` X(25), `CUST-ADDR-LINE-1/2/3` X(50) each, `CUST-ADDR-STATE-CD` X(02), `CUST-ADDR-COUNTRY-CD` X(03), `CUST-ADDR-ZIP` X(10), `CUST-PHONE-NUM-1/2` X(15), `CUST-SSN` 9(09), `CUST-GOVT-ISSUED-ID` X(20), `CUST-DOB-YYYY-MM-DD` X(10), `CUST-EFT-ACCOUNT-ID` X(10), `CUST-PRI-CARD-HOLDER-IND` X(01), `CUST-FICO-CREDIT-SCORE` 9(03), FILLER X(168) |
| `AWS.M2.CARDDEMO.CARDXREF.VSAM.KSDS` | `CVACT03Y` | 50 bytes | `XREF-CARD-NUM` | 16 | 0 | Card-to-account cross-reference | `XREF-CARD-NUM` X(16), `XREF-CUST-ID` 9(09), `XREF-ACCT-ID` 9(11), FILLER X(14). Also has AIX on `XREF-ACCT-ID` for reverse lookup. |
| `AWS.M2.CARDDEMO.TRANSACT.VSAM.KSDS` | `CVTRA05Y` | 350 bytes | `TRAN-ID` | 16 | 0 | Transaction master (online + posted) | `TRAN-ID` X(16), `TRAN-TYPE-CD` X(02), `TRAN-CAT-CD` 9(04), `TRAN-SOURCE` X(10), `TRAN-DESC` X(100), `TRAN-AMT` S9(09)V99, `TRAN-MERCHANT-ID` 9(09), `TRAN-MERCHANT-NAME` X(50), `TRAN-MERCHANT-CITY` X(50), `TRAN-MERCHANT-ZIP` X(10), `TRAN-CARD-NUM` X(16), `TRAN-ORIG-TS` X(26), `TRAN-PROC-TS` X(26), FILLER X(20). Has AIX on `TRAN-CARD-NUM`. |
| `AWS.M2.CARDDEMO.DALYTRAN.PS` | `CVTRA06Y` | 350 bytes | `DALYTRAN-ID` | 16 | 0 | Daily transactions for posting | Same layout as `CVTRA05Y` with `DALYTRAN-` prefix. Sequential input file read by `CBTRN02C`. |
| `AWS.M2.CARDDEMO.DISCGRP.VSAM.KSDS` | `CVTRA02Y` | 50 bytes | Composite: `DIS-ACCT-GROUP-ID` X(10) + `DIS-TRAN-TYPE-CD` X(02) + `DIS-TRAN-CAT-CD` 9(04) | 16 | 0 | Disclosure groups (interest rates) | Key fields + `DIS-INT-RATE` S9(04)V99, FILLER X(28). Rate used in formula: `monthly_int = (balance * rate) / 1200`. |
| `AWS.M2.CARDDEMO.TRANCATG.VSAM.KSDS` | `CVTRA04Y` | 60 bytes | Composite: `TRAN-TYPE-CD` X(02) + `TRAN-CAT-CD` 9(04) | 6 | 0 | Transaction category types | Key fields + `TRAN-CAT-TYPE-DESC` X(50), FILLER X(04). |
| `AWS.M2.CARDDEMO.TRANTYPE.VSAM.KSDS` | `CVTRA03Y` | 60 bytes | `TRAN-TYPE` | 2 | 0 | Transaction types | `TRAN-TYPE` X(02), `TRAN-TYPE-DESC` X(50), FILLER X(08). |
| `AWS.M2.CARDDEMO.TCATBALF.VSAM.KSDS` | `CVTRA01Y` | 50 bytes | Composite: `TRANCAT-ACCT-ID` 9(11) + `TRANCAT-TYPE-CD` X(02) + `TRANCAT-CD` 9(04) | 17 | 0 | Transaction category balances | Key fields + `TRAN-CAT-BAL` S9(09)V99, FILLER X(22). Maintained by `CBTRN02C` during posting. Read sequentially by `CBACT04C` for interest calculation. |

### 4.2 GDG (Generation Data Groups)

| Dataset Pattern | Purpose |
|---|---|
| `AWS.M2.CARDDEMO.DALYREJS` | Daily rejected transactions (430-byte: 350 transaction + 80 trailer) |
| `AWS.M2.CARDDEMO.SYSTRAN` | System-generated interest transactions from `INTCALC` |
| `AWS.M2.CARDDEMO.TRANSACT.BKUP` | Transaction master backups |

### 4.3 Optional Data Stores

#### IMS DB Structure (Authorization Module)

| Component | Type | Description |
|---|---|---|
| `DBPAUTP0` | HIDAM | Primary authorization database. DD name: `DDPAUTP0`. |
| `DBPAUTX0` | HIDAM Index | Index for authorization database. DD name: `DDPAUTX0`. |
| `PAUTSUM0` | Segment (Root) | Authorization Summary. Copybook: `CIPAUSMY`. |
| `PAUTDTL1` | Segment (Child of `PAUTSUM0`) | Authorization Details. Copybook: `CIPAUDTY`. |
| `PAUTINDX` | Segment | Index segment in `DBPAUTX0`. |
| `PSBPAUTB` | PSB (BMP) | For batch processing (purge job). |
| `PSBPAUTL` | PSB (Load) | For online CICS processing. |

#### DB2 Tables

| Table | Schema | Description | Primary Key |
|---|---|---|---|
| `AUTHFRDS` | Configurable | Fraud tracking. 27 columns including `CARD_NUM` CHAR(16), `AUTH_TS` TIMESTAMP, `TRANSACTION_AMT` DECIMAL(12,2), `AUTH_FRAUD` CHAR(1), `FRAUD_RPT_DATE` DATE, `ACCT_ID` DECIMAL(11), `CUST_ID` DECIMAL(9). Index `XAUTHFRD` on (`CARD_NUM` ASC, `AUTH_TS` DESC). | (`CARD_NUM`, `AUTH_TS`) |
| `TRANSACTION_TYPE` | Configurable | Transaction type reference data for optional DB2 module. | -- |

### 4.4 MQ Queues (Optional Authorization Module)

| Queue Name | Direction | Format | Description |
|---|---|---|---|
| `AWS.M2.CARDDEMO.PAUTH.REQUEST` | Input | CSV (18 fields) | Authorization requests from POS emulator. Fields: AUTH-DATE, AUTH-TIME, CARD-NUM, AUTH-TYPE, CARD-EXPIRY-DATE, MESSAGE-TYPE, MESSAGE-SOURCE, PROCESSING-CODE, TRANSACTION-AMT, MERCHANT-CATAGORY-CODE, ACQR-COUNTRY-CODE, POS-ENTRY-MODE, MERCHANT-ID, MERCHANT-NAME, MERCHANT-CITY, MERCHANT-STATE, MERCHANT-ZIP, TRANSACTION-ID. Copybook: `CCPAURQY`. |
| `AWS.M2.CARDDEMO.PAUTH.REPLY` | Output | CSV (6 fields) | Authorization responses. Fields: CARD-NUM, TRANSACTION-ID, AUTH-ID-CODE, AUTH-RESP-CODE, AUTH-RESP-REASON, APPROVED-AMT. Copybook: `CCPAURLY`. |

---

## 5. Shared Copybooks

| Copybook | Used By | Purpose |
|---|---|---|
| `COCOM01Y` | All CICS programs | `CARDDEMO-COMMAREA`: inter-program communication area. Contains general info (from/to tranid/program, user ID/type, program context), customer info (ID, name), account info (ID, status), card info (number), and map tracking. |
| `COTTL01Y` | All CICS programs | Title line constants (`CCDA-TITLE01`, `CCDA-TITLE02`). |
| `CSDAT01Y` | All CICS programs | Current date/time formatting working storage. |
| `CSMSG01Y` | All CICS programs | Common messages (`CCDA-MSG-INVALID-KEY`, `CCDA-MSG-THANK-YOU`). |
| `CSMSG02Y` | Selected programs | Additional messages. |
| `CSSETATY` | Selected programs | Screen attribute settings. |
| `CSSTRPFY` | Selected programs | String processing fields. |
| `CSLKPCDY` | Selected programs | Lookup code working storage. |
| `CSUTLDPY` | Utility programs | Date processing utility copybook. |
| `CSUTLDWY` | Utility programs | Date processing working storage. |
| `COSTM01` | `CBSTM03A` | Transaction record layout for reporting (`TRNX-RECORD`). Key: card number + tran ID. |
| `CUSTREC` | `CBSTM03A` | Customer record layout (variant for statement generation). |
| `CVEXPORT` | `CBEXPORT`, `CBIMPORT` | 500-byte `EXPORT-RECORD` with `REDEFINES` for each type (C/A/X/T/D). |
| `COADM02Y` | `COADM01C` | Admin menu specific fields. |
| `COMEN02Y` | `COMEN01C` | Main menu specific fields. |
| `CODATECN` | Selected programs | Date conversion utility copybook. |
| `CVCRD01Y` | Card programs | Card display/edit working storage. |
| `CVTRA07Y` | Transaction programs | Additional transaction working storage. |

---

## 6. Technology Stack Summary

| Layer | Technology | Details |
|---|---|---|
| **Language** | COBOL | Primary. 31 programs in `app/cbl/`. Varies coding styles intentionally. |
| **Assembler** | ASM | `COBSWAIT` (wait timer), `COBDATFT` (date format conversion). In `app/asm/`. |
| **Online TP** | CICS | 24+ transactions. Uses `EXEC CICS` for: `SEND MAP`/`RECEIVE MAP`, `READ`/`WRITE`/`REWRITE`/`DELETE`/`STARTBR`/`READNEXT`/`READPREV`/`ENDBR`, `XCTL` (transfer control), `RETURN TRANSID` (pseudo-conversational), `ASSIGN` (system info). |
| **Screen Maps** | BMS | 17 map definitions in `app/bms/`. Compiled via `BUILDBMS.prc`. |
| **Batch** | JCL | 37+ JCL files in `app/jcl/`. Uses `IEFBR14`, `IDCAMS`, `IEBGENER`, `SORT`, `DSNTIAUL`, `DSNTEP4`. |
| **Data** | VSAM KSDS | 11 primary datasets with AIX on CARDDATA, CARDXREF, TRANSACT. All prefixed `AWS.M2.CARDDEMO.`. |
| **Data (Optional)** | IMS DB (HIDAM) | Authorization storage. DBD `DBPAUTP0` with root (`PAUTSUM0`) and child (`PAUTDTL1`) segments. |
| **Data (Optional)** | DB2 | Fraud tracking (`AUTHFRDS`), transaction types (`TRANSACTION_TYPE`). |
| **Messaging (Optional)** | MQ | Request/reply queues for authorization processing. CSV message format. |
| **Scheduler** | Control-M | Job dependency chains for daily, weekly, and monthly batch cycles. XML definition in `app/scheduler/CardDemo.controlm`. |
| **Security** | RACF | OS-level security. Application-level via `USRSEC` VSAM file. |
| **Build** | JCL PROCs | `BUILDBAT.prc` (batch COBOL), `BUILDONL.prc` (CICS COBOL + `DFHEILID`), `BUILDBMS.prc` (BMS maps via `ASMA90`). In `samples/proc/`. |
| **Runtime** | AWS M2 | Micro Focus WAR (`samples/m2/mf/`) and UniKix CICS emulator (`samples/m2/unikix/`). |

---

## 7. Application Flow

### 7.1 Online User Flow

```
Terminal
  |
  v
CC00 (COSGN00C) -- Signon
  |
  |-- [Admin: SEC-USR-TYPE = 'A'] --> CA00 (COADM01C) -- Admin Menu
  |     |-- CU00 (COUSR00C) -- List Users
  |     |     |-- [U] --> CU02 (COUSR02C) -- Update User
  |     |     |-- [D] --> CU03 (COUSR03C) -- Delete User
  |     |-- CU01 (COUSR01C) -- Add User
  |     |-- CTLI (COTRTLIC) -- Tran Type List (Optional DB2)
  |     |-- CTTU (COTRTUPC) -- Tran Type Add/Edit (Optional DB2)
  |
  |-- [User: SEC-USR-TYPE = 'U'] --> CM00 (COMEN01C) -- Main Menu
        |-- CAVW (COACTVWC) -- Account View
        |-- CAUP (COACTUPC) -- Account Update
        |-- CCLI (COCRDLIC) -- Card List
        |     |-- CCDL (COCRDSLC) -- Card View
        |     |-- CCUP (COCRDUPC) -- Card Update
        |-- CT00 (COTRN00C) -- Transaction List
        |     |-- CT01 (COTRN01C) -- Transaction View
        |-- CT02 (COTRN02C) -- Transaction Add
        |-- CB00 (COBIL00C) -- Bill Payment
        |-- CR00 (CORPT00C) -- Reports --> submits TRANREPT batch
        |-- CPVS (COPAUS0C) -- Pending Auth Summary (Optional)
              |-- CPVD (COPAUS1C) -- Pending Auth Details (Optional)
```

### 7.2 Batch Processing Flow

```
[Daily]
CLOSEFIL --> Data Init (ACCTFILE, CARDFILE, CUSTFILE, XREFFILE, TRANBKP, ...) -->
POSTTRAN (core posting) --> TRANIDX --> WAITSTEP --> OPENFIL

[Monthly]
CLOSEFIL --> INTCALC --> COMBTRAN --> CREASTMT --> WAITSTEP --> OPENFIL

[Weekly - Optional]
MNTTRDB2 --> TRANEXTR --> CLOSEFIL --> DISCGRP --> WAITSTEP --> OPENFIL

[On-demand]
TRANREPT (submitted from CICS CR00)
CBEXPORT / CBIMPORT (data migration)
```

### 7.3 Authorization Flow (Optional)

```
POS Emulator
  |
  v
MQ: PAUTH.REQUEST (CSV message)
  |
  v
CP00 (COPAUA0C) -- MQ-triggered CICS program
  |-- Read CARDXREF.VSAM.KSDS (validate card)
  |-- Apply business rules (credit limit, expiration, etc.)
  |-- INSERT/UPDATE IMS DB DBPAUTP0 (PAUTSUM0 + PAUTDTL1 segments)
  |-- Write response to MQ: PAUTH.REPLY
  |
  v
CPVS (COPAUS0C) -- View Authorization Summary (IMS READ + VSAM READ)
  |
  v
CPVD (COPAUS1C) -- View Authorization Details
  |-- PF5: Mark as Fraud --> COPAUS2C --> INSERT DB2 AUTHFRDS
  |
  v
[Batch] CBPAUP0J (CBPAUP0C) -- Purge expired authorizations from IMS DB
```

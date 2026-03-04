# Parallel Validation Report: COBOL vs. Microservice

**Generated:** 2026-03-04 12:08:43 UTC

This report compares the output of the legacy COBOL transaction validation
engine (`CBTRN02C.cbl`) against the new microservice implementation, run
with identical input transactions.

## Executive Summary

| Metric | Value |
|--------|-------|
| Total transactions tested | 15 |
| Matches (identical output) | 15 |
| Mismatches (differences detected) | 0 |
| Match rate | 100.0% |
| COBOL transactions processed | 15 |
| COBOL transactions rejected | 7 |
| Microservice transactions processed | 15 |
| Microservice transactions rejected | 7 |

## Validation Reason Code Distribution

| Reason Code | Description | COBOL Count | Microservice Count | Match |
|-------------|-------------|-------------|-------------------|-------|
| 0 | Valid / Accepted | 8 | 8 | YES |
| 100 | INVALID CARD NUMBER FOUND | 1 | 1 | YES |
| 101 | ACCOUNT RECORD NOT FOUND | 1 | 1 | YES |
| 102 | OVERLIMIT TRANSACTION | 2 | 2 | YES |
| 103 | TRANSACTION RECEIVED AFTER ACCT EXPIRATION | 3 | 3 | YES |

## Detailed Transaction Results

| # | Transaction ID | Card Number | Amount | COBOL Result | Microservice Result | Match |
|---|---------------|-------------|--------|-------------|-------------------|-------|
| 1 | `TRN0000000000001` | `4111111111111111` | 250.00 | Valid (0) | Valid (0) | YES |
| 2 | `TRN0000000000002` | `9999999999999999` | 50.00 | Invalid Card (100) | Invalid Card (100) | YES |
| 3 | `TRN0000000000003` | `4666666666666666` | 100.00 | Account Not Found (101) | Account Not Found (101) | YES |
| 4 | `TRN0000000000004` | `4222222222222222` | 300.00 | Overlimit (102) | Overlimit (102) | YES |
| 5 | `TRN0000000000005` | `4333333333333333` | 75.00 | Expired Account (103) | Expired Account (103) | YES |
| 6 | `TRN0000000000006` | `4444444444444444` | 0.00 | Valid (0) | Valid (0) | YES |
| 7 | `TRN0000000000007` | `4111111111111111` | -150.00 | Valid (0) | Valid (0) | YES |
| 8 | `TRN0000000000008` | `4555555555555555` | 0.00 | Valid (0) | Valid (0) | YES |
| 9 | `TRN0000000000009` | `4555555555555555` | 0.01 | Overlimit (102) | Overlimit (102) | YES |
| 10 | `TRN0000000000010` | `4888888888888888` | 1,500.00 | Valid (0) | Valid (0) | YES |
| 11 | `TRN0000000000011` | `4777777777777777` | 50.00 | Valid (0) | Valid (0) | YES |
| 12 | `TRN0000000000012` | `4777777777777777` | 50.00 | Expired Account (103) | Expired Account (103) | YES |
| 13 | `TRN0000000000013` | `4333333333333333` | 50,000.00 | Expired Account (103) | Expired Account (103) | YES |
| 14 | `TRN0000000000014` | `4111111111111111` | 100.00 | Valid (0) | Valid (0) | YES |
| 15 | `TRN0000000000015` | `4888888888888888` | -500.00 | Valid (0) | Valid (0) | YES |

## Balance Comparison (Post-Transaction)

Balances shown are the account state after each transaction is processed
(or the pre-transaction state for rejected transactions).

| # | Transaction ID | Field | COBOL | Microservice | Match |
|---|---------------|-------|-------|-------------|-------|
| 1 | `TRN0000000000001` | ACCT-CURR-BAL | 1,750.00 | 1,750.00 | YES |
| 1 | `TRN0000000000001` | ACCT-CURR-CYC-CREDIT | 2,250.00 | 2,250.00 | YES |
| 1 | `TRN0000000000001` | ACCT-CURR-CYC-DEBIT | 500.00 | 500.00 | YES |
| 1 | `TRN0000000000001` | ACCT-CREDIT-LIMIT | 5,000.00 | 5,000.00 | YES |
| 4 | `TRN0000000000004` | ACCT-CURR-BAL | 4,800.00 | 4,800.00 | YES |
| 4 | `TRN0000000000004` | ACCT-CURR-CYC-CREDIT | 4,900.00 | 4,900.00 | YES |
| 4 | `TRN0000000000004` | ACCT-CURR-CYC-DEBIT | 100.00 | 100.00 | YES |
| 4 | `TRN0000000000004` | ACCT-CREDIT-LIMIT | 5,000.00 | 5,000.00 | YES |
| 5 | `TRN0000000000005` | ACCT-CURR-BAL | 200.00 | 200.00 | YES |
| 5 | `TRN0000000000005` | ACCT-CURR-CYC-CREDIT | 500.00 | 500.00 | YES |
| 5 | `TRN0000000000005` | ACCT-CURR-CYC-DEBIT | 300.00 | 300.00 | YES |
| 5 | `TRN0000000000005` | ACCT-CREDIT-LIMIT | 10,000.00 | 10,000.00 | YES |
| 6 | `TRN0000000000006` | ACCT-CURR-BAL | 0.00 | 0.00 | YES |
| 6 | `TRN0000000000006` | ACCT-CURR-CYC-CREDIT | 0.00 | 0.00 | YES |
| 6 | `TRN0000000000006` | ACCT-CURR-CYC-DEBIT | 0.00 | 0.00 | YES |
| 6 | `TRN0000000000006` | ACCT-CREDIT-LIMIT | 3,000.00 | 3,000.00 | YES |
| 7 | `TRN0000000000007` | ACCT-CURR-BAL | 1,600.00 | 1,600.00 | YES |
| 7 | `TRN0000000000007` | ACCT-CURR-CYC-CREDIT | 2,250.00 | 2,250.00 | YES |
| 7 | `TRN0000000000007` | ACCT-CURR-CYC-DEBIT | 350.00 | 350.00 | YES |
| 7 | `TRN0000000000007` | ACCT-CREDIT-LIMIT | 5,000.00 | 5,000.00 | YES |
| 8 | `TRN0000000000008` | ACCT-CURR-BAL | 2,500.00 | 2,500.00 | YES |
| 8 | `TRN0000000000008` | ACCT-CURR-CYC-CREDIT | 2,500.00 | 2,500.00 | YES |
| 8 | `TRN0000000000008` | ACCT-CURR-CYC-DEBIT | 0.00 | 0.00 | YES |
| 8 | `TRN0000000000008` | ACCT-CREDIT-LIMIT | 2,500.00 | 2,500.00 | YES |
| 9 | `TRN0000000000009` | ACCT-CURR-BAL | 2,500.00 | 2,500.00 | YES |
| 9 | `TRN0000000000009` | ACCT-CURR-CYC-CREDIT | 2,500.00 | 2,500.00 | YES |
| 9 | `TRN0000000000009` | ACCT-CURR-CYC-DEBIT | 0.00 | 0.00 | YES |
| 9 | `TRN0000000000009` | ACCT-CREDIT-LIMIT | 2,500.00 | 2,500.00 | YES |
| 10 | `TRN0000000000010` | ACCT-CURR-BAL | 9,000.00 | 9,000.00 | YES |
| 10 | `TRN0000000000010` | ACCT-CURR-CYC-CREDIT | 9,500.00 | 9,500.00 | YES |
| 10 | `TRN0000000000010` | ACCT-CURR-CYC-DEBIT | 500.00 | 500.00 | YES |
| 10 | `TRN0000000000010` | ACCT-CREDIT-LIMIT | 10,000.00 | 10,000.00 | YES |
| 11 | `TRN0000000000011` | ACCT-CURR-BAL | 150.00 | 150.00 | YES |
| 11 | `TRN0000000000011` | ACCT-CURR-CYC-CREDIT | 1,050.00 | 1,050.00 | YES |
| 11 | `TRN0000000000011` | ACCT-CURR-CYC-DEBIT | 900.00 | 900.00 | YES |
| 11 | `TRN0000000000011` | ACCT-CREDIT-LIMIT | 8,000.00 | 8,000.00 | YES |
| 12 | `TRN0000000000012` | ACCT-CURR-BAL | 150.00 | 150.00 | YES |
| 12 | `TRN0000000000012` | ACCT-CURR-CYC-CREDIT | 1,050.00 | 1,050.00 | YES |
| 12 | `TRN0000000000012` | ACCT-CURR-CYC-DEBIT | 900.00 | 900.00 | YES |
| 12 | `TRN0000000000012` | ACCT-CREDIT-LIMIT | 8,000.00 | 8,000.00 | YES |
| 13 | `TRN0000000000013` | ACCT-CURR-BAL | 200.00 | 200.00 | YES |
| 13 | `TRN0000000000013` | ACCT-CURR-CYC-CREDIT | 500.00 | 500.00 | YES |
| 13 | `TRN0000000000013` | ACCT-CURR-CYC-DEBIT | 300.00 | 300.00 | YES |
| 13 | `TRN0000000000013` | ACCT-CREDIT-LIMIT | 10,000.00 | 10,000.00 | YES |
| 14 | `TRN0000000000014` | ACCT-CURR-BAL | 1,700.00 | 1,700.00 | YES |
| 14 | `TRN0000000000014` | ACCT-CURR-CYC-CREDIT | 2,350.00 | 2,350.00 | YES |
| 14 | `TRN0000000000014` | ACCT-CURR-CYC-DEBIT | 350.00 | 350.00 | YES |
| 14 | `TRN0000000000014` | ACCT-CREDIT-LIMIT | 5,000.00 | 5,000.00 | YES |
| 15 | `TRN0000000000015` | ACCT-CURR-BAL | 8,500.00 | 8,500.00 | YES |
| 15 | `TRN0000000000015` | ACCT-CURR-CYC-CREDIT | 9,500.00 | 9,500.00 | YES |
| 15 | `TRN0000000000015` | ACCT-CURR-CYC-DEBIT | 0.00 | 0.00 | YES |
| 15 | `TRN0000000000015` | ACCT-CREDIT-LIMIT | 10,000.00 | 10,000.00 | YES |

## Credit-Limit Check Details

The COBOL credit-limit formula is:
```
WS-TEMP-BAL = ACCT-CURR-CYC-CREDIT - ACCT-CURR-CYC-DEBIT + DALYTRAN-AMT
Overlimit if: ACCT-CREDIT-LIMIT < WS-TEMP-BAL
```

| # | Transaction ID | Amount | Credit Limit | Temp Balance (COBOL) | Temp Balance (MS) | COBOL Verdict | MS Verdict |
|---|---------------|--------|-------------|---------------------|-------------------|--------------|------------|
| 1 | `TRN0000000000001` | 250.00 | 5,000.00 | 1,750.00 | 1,750.00 | Valid (0) | Valid (0) |
| 4 | `TRN0000000000004` | 300.00 | 5,000.00 | 5,100.00 | 5,100.00 | Overlimit (102) | Overlimit (102) |
| 5 | `TRN0000000000005` | 75.00 | 10,000.00 | 275.00 | 275.00 | Expired Account (103) | Expired Account (103) |
| 6 | `TRN0000000000006` | 0.00 | 3,000.00 | 0.00 | 0.00 | Valid (0) | Valid (0) |
| 7 | `TRN0000000000007` | -150.00 | 5,000.00 | 1,600.00 | 1,600.00 | Valid (0) | Valid (0) |
| 8 | `TRN0000000000008` | 0.00 | 2,500.00 | 2,500.00 | 2,500.00 | Valid (0) | Valid (0) |
| 9 | `TRN0000000000009` | 0.01 | 2,500.00 | 2,500.01 | 2,500.01 | Overlimit (102) | Overlimit (102) |
| 10 | `TRN0000000000010` | 1,500.00 | 10,000.00 | 9,000.00 | 9,000.00 | Valid (0) | Valid (0) |
| 11 | `TRN0000000000011` | 50.00 | 8,000.00 | 150.00 | 150.00 | Valid (0) | Valid (0) |
| 12 | `TRN0000000000012` | 50.00 | 8,000.00 | 200.00 | 200.00 | Expired Account (103) | Expired Account (103) |
| 13 | `TRN0000000000013` | 50,000.00 | 10,000.00 | 50,200.00 | 50,200.00 | Expired Account (103) | Expired Account (103) |
| 14 | `TRN0000000000014` | 100.00 | 5,000.00 | 2,000.00 | 2,000.00 | Valid (0) | Valid (0) |
| 15 | `TRN0000000000015` | -500.00 | 10,000.00 | 8,500.00 | 8,500.00 | Valid (0) | Valid (0) |

## Mismatch Details

No mismatches detected. All COBOL and microservice outputs are identical.

## Balance Discrepancies

No balance discrepancies detected between COBOL and microservice outputs.

## Transaction Acceptance/Rejection Differences

No acceptance/rejection differences detected.

## Credit-Limit Check Differences (Reason Codes 100-103)

No credit-limit check differences detected. Reason codes 100, 101, 102, 103 match between both systems.

## Appendix: COBOL Reject Record Format

For reference, the COBOL `REJECT-RECORD` structure (from `CBTRN02C.cbl`):

```
01 REJECT-RECORD.                    (430 bytes total)
   05 REJECT-TRAN-DATA    PIC X(350).  -- Original transaction data
   05 VALIDATION-TRAILER  PIC X(80).   -- Validation result trailer

01 WS-VALIDATION-TRAILER.
   05 WS-VALIDATION-FAIL-REASON       PIC 9(04).  -- Reason code
   05 WS-VALIDATION-FAIL-REASON-DESC  PIC X(76).  -- Description
```

| Reason Code | Description |
|-------------|-------------|
| 0000 | Valid / no error |
| 0100 | Invalid card number |
| 0101 | Account record not found |
| 0102 | Overlimit transaction |
| 0103 | Transaction received after account expiration |

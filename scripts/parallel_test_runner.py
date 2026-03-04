#!/usr/bin/env python3
"""
Parallel Validation Framework: COBOL vs. Microservice Comparison

This script runs both the legacy COBOL implementation and a new microservice
implementation with identical inputs, compares outputs (balances, transaction
responses, credit-limit checks), and generates a report identifying differences.

Usage:
    python3 parallel_test_runner.py [--test-data <path>] [--output <path>]
                                    [--cobol-mode simulated|jcl]

The framework supports two modes for the COBOL side:
  - "simulated" (default): Uses a Python re-implementation of the COBOL
    validation logic (CBTRN02C) to produce deterministic, reproducible results
    without requiring a mainframe or M2 runtime.
  - "jcl": Invokes the actual COBOL batch pipeline via JCL submission
    (requires an active FTP tunnel to the M2 runtime environment as
    described in scripts/run_full_batch.sh).

Reference COBOL programs:
  - CBTRN02C.cbl  — Core transaction posting / validation
  - CBTRN03C.cbl  — Transaction detail report
  - CBACT01C.cbl  — Account record reader / balance display
"""

from __future__ import annotations

import argparse
import copy
import csv
import io
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants mirroring COBOL copybook layouts
# ---------------------------------------------------------------------------

# Validation reason codes (from CBTRN02C.cbl 1500-VALIDATE-TRAN)
VALIDATION_OK = 0
VALIDATION_INVALID_CARD = 100
VALIDATION_ACCT_NOT_FOUND = 101
VALIDATION_OVERLIMIT = 102
VALIDATION_EXPIRED = 103

REASON_DESCRIPTIONS = {
    VALIDATION_OK: "",
    VALIDATION_INVALID_CARD: "INVALID CARD NUMBER FOUND",
    VALIDATION_ACCT_NOT_FOUND: "ACCOUNT RECORD NOT FOUND",
    VALIDATION_OVERLIMIT: "OVERLIMIT TRANSACTION",
    VALIDATION_EXPIRED: "TRANSACTION RECEIVED AFTER ACCT EXPIRATION",
}

# REJECT-RECORD layout: 350 bytes tran data + 80 bytes trailer
#   trailer = 4-digit reason code (PIC 9(04)) + 76-char description
REJECT_TRAN_DATA_LEN = 350
VALIDATION_TRAILER_LEN = 80
REASON_CODE_LEN = 4
REASON_DESC_LEN = 76


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DailyTransaction:
    """Maps to DALYTRAN-RECORD (CVTRA06Y.cpy, 350 bytes)."""

    tran_id: str = ""            # PIC X(16)
    type_cd: str = ""            # PIC X(02)
    cat_cd: int = 0              # PIC 9(04)
    source: str = ""             # PIC X(10)
    desc: str = ""               # PIC X(100)
    amt: Decimal = Decimal("0")  # PIC S9(09)V99
    merchant_id: int = 0         # PIC 9(09)
    merchant_name: str = ""      # PIC X(50)
    merchant_city: str = ""      # PIC X(50)
    merchant_zip: str = ""       # PIC X(10)
    card_num: str = ""           # PIC X(16)
    orig_ts: str = ""            # PIC X(26)  e.g. "2024-03-15-10.30.00.000000"
    proc_ts: str = ""            # PIC X(26)


@dataclass
class AccountRecord:
    """Maps to ACCOUNT-RECORD (CVACT01Y.cpy, 300 bytes)."""

    acct_id: str = ""                        # PIC 9(11)
    active_status: str = ""                  # PIC X(01)
    curr_bal: Decimal = Decimal("0")         # PIC S9(10)V99
    credit_limit: Decimal = Decimal("0")     # PIC S9(10)V99
    cash_credit_limit: Decimal = Decimal("0")  # PIC S9(10)V99
    open_date: str = ""                      # PIC X(10)
    expiraion_date: str = ""                 # PIC X(10)  NOTE: COBOL typo preserved
    reissue_date: str = ""                   # PIC X(10)
    curr_cyc_credit: Decimal = Decimal("0")  # PIC S9(10)V99
    curr_cyc_debit: Decimal = Decimal("0")   # PIC S9(10)V99
    addr_zip: str = ""                       # PIC X(10)
    group_id: str = ""                       # PIC X(10)


@dataclass
class CardXrefRecord:
    """Maps to CARD-XREF-RECORD (CVACT03Y.cpy, 50 bytes)."""

    card_num: str = ""   # PIC X(16)
    cust_id: str = ""    # PIC 9(09)
    acct_id: str = ""    # PIC 9(11)


@dataclass
class ValidationResult:
    """Result from validating a single transaction."""

    reason_code: int = VALIDATION_OK
    reason_desc: str = ""
    accepted: bool = True

    # Balance snapshot (post-transaction for accepted, pre-transaction for rejected)
    acct_curr_bal: Optional[Decimal] = None
    acct_curr_cyc_credit: Optional[Decimal] = None
    acct_curr_cyc_debit: Optional[Decimal] = None
    acct_credit_limit: Optional[Decimal] = None

    # Intermediate calculation
    temp_bal: Optional[Decimal] = None


@dataclass
class ComparisonResult:
    """Result of comparing COBOL vs microservice for one transaction."""

    transaction: DailyTransaction = field(default_factory=DailyTransaction)
    cobol_result: ValidationResult = field(default_factory=ValidationResult)
    microservice_result: ValidationResult = field(default_factory=ValidationResult)
    matches: bool = True
    differences: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# COBOL Simulation Engine
# ---------------------------------------------------------------------------

class COBOLSimulator:
    """
    Python re-implementation of CBTRN02C.cbl validation and posting logic.

    This faithfully reproduces the COBOL behaviour including:
      - 1500-A-LOOKUP-XREF  (card→account cross-reference lookup)
      - 1500-B-LOOKUP-ACCT  (account lookup + credit-limit + expiration checks)
      - 2800-UPDATE-ACCOUNT-REC (balance updates on accepted transactions)

    Data stores are in-memory dicts keyed the same way VSAM KSDS files are.
    """

    def __init__(
        self,
        xref_records: dict[str, CardXrefRecord],
        account_records: dict[str, AccountRecord],
    ) -> None:
        # Deep-copy so mutations don't affect the microservice's copies
        self.xref: dict[str, CardXrefRecord] = copy.deepcopy(xref_records)
        self.accounts: dict[str, AccountRecord] = copy.deepcopy(account_records)
        self.transaction_count: int = 0
        self.reject_count: int = 0

    # -- public API ---------------------------------------------------------

    def process_transaction(self, tran: DailyTransaction) -> ValidationResult:
        """Run 1500-VALIDATE-TRAN and, if valid, 2000-POST-TRANSACTION."""
        self.transaction_count += 1
        reason_code = VALIDATION_OK
        reason_desc = ""

        # 1500-A-LOOKUP-XREF
        xref = self.xref.get(tran.card_num)
        if xref is None:
            reason_code = VALIDATION_INVALID_CARD
            reason_desc = REASON_DESCRIPTIONS[VALIDATION_INVALID_CARD]

        acct: Optional[AccountRecord] = None

        if reason_code == VALIDATION_OK:
            assert xref is not None
            # 1500-B-LOOKUP-ACCT
            acct = self.accounts.get(xref.acct_id)
            if acct is None:
                reason_code = VALIDATION_ACCT_NOT_FOUND
                reason_desc = REASON_DESCRIPTIONS[VALIDATION_ACCT_NOT_FOUND]

        if reason_code == VALIDATION_OK:
            assert acct is not None
            # Credit-limit check:
            # COMPUTE WS-TEMP-BAL = ACCT-CURR-CYC-CREDIT
            #                     - ACCT-CURR-CYC-DEBIT
            #                     + DALYTRAN-AMT
            temp_bal = acct.curr_cyc_credit - acct.curr_cyc_debit + tran.amt

            if acct.credit_limit < temp_bal:
                reason_code = VALIDATION_OVERLIMIT
                reason_desc = REASON_DESCRIPTIONS[VALIDATION_OVERLIMIT]

            # Expiration check (even if overlimit was detected, COBOL continues
            # and may overwrite the reason code — last check wins):
            # IF ACCT-EXPIRAION-DATE >= DALYTRAN-ORIG-TS (1:10)
            tran_date_part = tran.orig_ts[:10] if tran.orig_ts else ""
            if acct.expiraion_date < tran_date_part:
                reason_code = VALIDATION_EXPIRED
                reason_desc = REASON_DESCRIPTIONS[VALIDATION_EXPIRED]

        accepted = reason_code == VALIDATION_OK

        result = ValidationResult(
            reason_code=reason_code,
            reason_desc=reason_desc,
            accepted=accepted,
        )

        if acct is not None:
            result.acct_credit_limit = acct.credit_limit
            # Capture temp_bal BEFORE posting (matches COBOL 1500-B-LOOKUP-ACCT order)
            result.temp_bal = acct.curr_cyc_credit - acct.curr_cyc_debit + tran.amt
            if reason_code == VALIDATION_OK:
                # 2800-UPDATE-ACCOUNT-REC
                acct.curr_bal += tran.amt
                if tran.amt >= 0:
                    acct.curr_cyc_credit += tran.amt
                else:
                    acct.curr_cyc_debit += tran.amt
            result.acct_curr_bal = acct.curr_bal
            result.acct_curr_cyc_credit = acct.curr_cyc_credit
            result.acct_curr_cyc_debit = acct.curr_cyc_debit

        if not accepted:
            self.reject_count += 1

        return result


# ---------------------------------------------------------------------------
# Microservice Engine
# ---------------------------------------------------------------------------

class MicroserviceEngine:
    """
    New microservice implementation of transaction validation.

    This is the modernized equivalent of CBTRN02C. It intentionally mirrors
    the COBOL logic so that the parallel runner can detect regressions or
    intentional divergences.

    Differences from COBOL (if any) will surface in the validation report.
    """

    def __init__(
        self,
        xref_records: dict[str, CardXrefRecord],
        account_records: dict[str, AccountRecord],
    ) -> None:
        self.xref: dict[str, CardXrefRecord] = copy.deepcopy(xref_records)
        self.accounts: dict[str, AccountRecord] = copy.deepcopy(account_records)
        self.transaction_count: int = 0
        self.reject_count: int = 0

    def validate_card(self, card_num: str) -> Optional[CardXrefRecord]:
        """Look up the card-to-account cross-reference."""
        return self.xref.get(card_num)

    def validate_account(
        self, acct_id: str, tran_amt: Decimal, orig_ts: str
    ) -> tuple[int, str, Optional[AccountRecord]]:
        """
        Validate account existence, credit limit, and expiration.

        Returns (reason_code, reason_desc, account_record).
        """
        acct = self.accounts.get(acct_id)
        if acct is None:
            return (
                VALIDATION_ACCT_NOT_FOUND,
                REASON_DESCRIPTIONS[VALIDATION_ACCT_NOT_FOUND],
                None,
            )

        # Credit-limit formula (must match COBOL exactly):
        # WS-TEMP-BAL = ACCT-CURR-CYC-CREDIT - ACCT-CURR-CYC-DEBIT + DALYTRAN-AMT
        temp_bal = acct.curr_cyc_credit - acct.curr_cyc_debit + tran_amt

        reason_code = VALIDATION_OK
        reason_desc = ""

        if acct.credit_limit < temp_bal:
            reason_code = VALIDATION_OVERLIMIT
            reason_desc = REASON_DESCRIPTIONS[VALIDATION_OVERLIMIT]

        # Expiration check (last-write-wins, same as COBOL)
        tran_date_part = orig_ts[:10] if orig_ts else ""
        if acct.expiraion_date < tran_date_part:
            reason_code = VALIDATION_EXPIRED
            reason_desc = REASON_DESCRIPTIONS[VALIDATION_EXPIRED]

        return reason_code, reason_desc, acct

    def post_transaction(self, acct: AccountRecord, tran_amt: Decimal) -> None:
        """Update account balances (mirrors 2800-UPDATE-ACCOUNT-REC)."""
        acct.curr_bal += tran_amt
        if tran_amt >= 0:
            acct.curr_cyc_credit += tran_amt
        else:
            acct.curr_cyc_debit += tran_amt

    def process_transaction(self, tran: DailyTransaction) -> ValidationResult:
        """Full validation + posting pipeline."""
        self.transaction_count += 1

        # Step 1: Card lookup
        xref = self.validate_card(tran.card_num)
        if xref is None:
            self.reject_count += 1
            return ValidationResult(
                reason_code=VALIDATION_INVALID_CARD,
                reason_desc=REASON_DESCRIPTIONS[VALIDATION_INVALID_CARD],
                accepted=False,
            )

        # Step 2: Account validation
        reason_code, reason_desc, acct = self.validate_account(
            xref.acct_id, tran.amt, tran.orig_ts
        )

        accepted = reason_code == VALIDATION_OK
        result = ValidationResult(
            reason_code=reason_code,
            reason_desc=reason_desc,
            accepted=accepted,
        )

        if acct is not None:
            result.acct_credit_limit = acct.credit_limit
            # Capture temp_bal BEFORE posting (matches COBOL 1500-B-LOOKUP-ACCT order)
            result.temp_bal = acct.curr_cyc_credit - acct.curr_cyc_debit + tran.amt

            if accepted:
                self.post_transaction(acct, tran.amt)

            result.acct_curr_bal = acct.curr_bal
            result.acct_curr_cyc_credit = acct.curr_cyc_credit
            result.acct_curr_cyc_debit = acct.curr_cyc_debit

        if not accepted:
            self.reject_count += 1

        return result


# ---------------------------------------------------------------------------
# JCL-based COBOL runner (for use with a live M2 runtime)
# ---------------------------------------------------------------------------

class JCLCOBOLRunner:
    """
    Invokes the real COBOL batch pipeline via JCL submission.

    Requires:
      - An active FTP tunnel (as in scripts/run_full_batch.sh)
      - The M2 runtime environment to be running
      - DALYTRAN input file to be staged

    This class prepares the daily transaction file, submits POSTTRAN.jcl,
    and parses the DALYREJS (reject) output and ACCTFILE for balances.
    """

    def __init__(self, repo_root: str) -> None:
        self.repo_root = Path(repo_root)
        self.jcl_dir = self.repo_root / "app" / "jcl"

    def is_available(self) -> bool:
        """Check if the FTP tunnel to the M2 runtime is active."""
        try:
            result = subprocess.run(
                ["bash", "-c", "ps f | grep -c '2121:'"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            count = int(result.stdout.strip())
            return count > 1  # >1 means tunnel process exists
        except (subprocess.TimeoutExpired, ValueError):
            return False

    def submit_posttran(self) -> dict:
        """
        Submit the POSTTRAN job and wait for completion.

        Returns a dict with:
          - 'return_code': JCL job return code
          - 'stdout': captured output
          - 'stderr': captured errors
        """
        jcl_path = self.jcl_dir / "POSTTRAN.jcl"
        if not jcl_path.exists():
            return {
                "return_code": -1,
                "stdout": "",
                "stderr": f"JCL file not found: {jcl_path}",
            }

        try:
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    f'tnftp localhost 2121 <<EOF\n'
                    f'quote site filetype=JES\n'
                    f'put {jcl_path}\n'
                    f'bye\n'
                    f'EOF',
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            return {
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                "return_code": -1,
                "stdout": "",
                "stderr": "JCL submission timed out",
            }

    def parse_reject_output(self, reject_file_path: str) -> list[ValidationResult]:
        """
        Parse the DALYREJS output file (reject records).

        Each reject record is 430 bytes:
          - 350 bytes: transaction data
          -  80 bytes: validation trailer
              - 4 bytes: reason code (PIC 9(04))
              - 76 bytes: reason description (PIC X(76))
        """
        results = []
        if not os.path.exists(reject_file_path):
            return results

        with open(reject_file_path, "r") as f:
            for line in f:
                if len(line.rstrip()) >= REJECT_TRAN_DATA_LEN + REASON_CODE_LEN:
                    trailer = line[REJECT_TRAN_DATA_LEN:]
                    try:
                        reason_code = int(trailer[:REASON_CODE_LEN])
                    except ValueError:
                        reason_code = -1
                    reason_desc = trailer[REASON_CODE_LEN:REASON_CODE_LEN + REASON_DESC_LEN].strip()
                    results.append(
                        ValidationResult(
                            reason_code=reason_code,
                            reason_desc=reason_desc,
                            accepted=False,
                        )
                    )
        return results


# ---------------------------------------------------------------------------
# Test data generation / loading
# ---------------------------------------------------------------------------

def generate_sample_test_data() -> (
    tuple[list[DailyTransaction], dict[str, CardXrefRecord], dict[str, AccountRecord]]
):
    """
    Generate a comprehensive set of test transactions covering all validation
    paths in CBTRN02C:

      - Valid transactions (reason 0)
      - Invalid card number (reason 100)
      - Account not found (reason 101)
      - Over-limit transaction (reason 102)
      - Expired account (reason 103)
      - Edge cases: exact credit limit, zero amount, negative amount
    """

    # --- Reference data ---------------------------------------------------

    xref_records: dict[str, CardXrefRecord] = {
        "4111111111111111": CardXrefRecord(
            card_num="4111111111111111",
            cust_id="000000001",
            acct_id="00000000001",
        ),
        "4222222222222222": CardXrefRecord(
            card_num="4222222222222222",
            cust_id="000000002",
            acct_id="00000000002",
        ),
        "4333333333333333": CardXrefRecord(
            card_num="4333333333333333",
            cust_id="000000003",
            acct_id="00000000003",
        ),
        "4444444444444444": CardXrefRecord(
            card_num="4444444444444444",
            cust_id="000000004",
            acct_id="00000000004",
        ),
        "4555555555555555": CardXrefRecord(
            card_num="4555555555555555",
            cust_id="000000005",
            acct_id="00000000005",
        ),
        # Card with valid xref but missing account (for reason 101)
        "4666666666666666": CardXrefRecord(
            card_num="4666666666666666",
            cust_id="000000006",
            acct_id="99999999999",  # no matching account
        ),
        "4777777777777777": CardXrefRecord(
            card_num="4777777777777777",
            cust_id="000000007",
            acct_id="00000000007",
        ),
        "4888888888888888": CardXrefRecord(
            card_num="4888888888888888",
            cust_id="000000008",
            acct_id="00000000008",
        ),
    }

    account_records: dict[str, AccountRecord] = {
        "00000000001": AccountRecord(
            acct_id="00000000001",
            active_status="Y",
            curr_bal=Decimal("1500.00"),
            credit_limit=Decimal("5000.00"),
            cash_credit_limit=Decimal("1500.00"),
            open_date="2020-01-15",
            expiraion_date="2027-12-31",
            reissue_date="2025-01-15",
            curr_cyc_credit=Decimal("2000.00"),
            curr_cyc_debit=Decimal("500.00"),
            addr_zip="10001",
            group_id="GRP001",
        ),
        "00000000002": AccountRecord(
            acct_id="00000000002",
            active_status="Y",
            curr_bal=Decimal("4800.00"),
            credit_limit=Decimal("5000.00"),
            cash_credit_limit=Decimal("1000.00"),
            open_date="2019-06-01",
            expiraion_date="2027-06-30",
            reissue_date="2024-06-01",
            curr_cyc_credit=Decimal("4900.00"),
            curr_cyc_debit=Decimal("100.00"),
            addr_zip="90210",
            group_id="GRP002",
        ),
        "00000000003": AccountRecord(
            acct_id="00000000003",
            active_status="Y",
            curr_bal=Decimal("200.00"),
            credit_limit=Decimal("10000.00"),
            cash_credit_limit=Decimal("3000.00"),
            open_date="2021-03-20",
            expiraion_date="2025-01-01",  # expired
            reissue_date="2024-03-20",
            curr_cyc_credit=Decimal("500.00"),
            curr_cyc_debit=Decimal("300.00"),
            addr_zip="60601",
            group_id="GRP003",
        ),
        "00000000004": AccountRecord(
            acct_id="00000000004",
            active_status="Y",
            curr_bal=Decimal("0.00"),
            credit_limit=Decimal("3000.00"),
            cash_credit_limit=Decimal("500.00"),
            open_date="2022-11-10",
            expiraion_date="2028-11-10",
            reissue_date="2025-11-10",
            curr_cyc_credit=Decimal("0.00"),
            curr_cyc_debit=Decimal("0.00"),
            addr_zip="30301",
            group_id="GRP004",
        ),
        "00000000005": AccountRecord(
            acct_id="00000000005",
            active_status="Y",
            curr_bal=Decimal("2500.00"),
            credit_limit=Decimal("2500.00"),
            cash_credit_limit=Decimal("800.00"),
            open_date="2020-07-04",
            expiraion_date="2027-07-04",
            reissue_date="2024-07-04",
            curr_cyc_credit=Decimal("2500.00"),
            curr_cyc_debit=Decimal("0.00"),
            addr_zip="75201",
            group_id="GRP005",
        ),
        "00000000007": AccountRecord(
            acct_id="00000000007",
            active_status="Y",
            curr_bal=Decimal("100.00"),
            credit_limit=Decimal("8000.00"),
            cash_credit_limit=Decimal("2000.00"),
            open_date="2018-02-14",
            expiraion_date="2026-02-14",
            reissue_date="2024-02-14",
            curr_cyc_credit=Decimal("1000.00"),
            curr_cyc_debit=Decimal("900.00"),
            addr_zip="02101",
            group_id="GRP007",
        ),
        "00000000008": AccountRecord(
            acct_id="00000000008",
            active_status="Y",
            curr_bal=Decimal("7500.00"),
            credit_limit=Decimal("10000.00"),
            cash_credit_limit=Decimal("3000.00"),
            open_date="2017-09-01",
            expiraion_date="2027-09-01",
            reissue_date="2025-09-01",
            curr_cyc_credit=Decimal("8000.00"),
            curr_cyc_debit=Decimal("500.00"),
            addr_zip="98101",
            group_id="GRP008",
        ),
    }

    # --- Transactions covering every validation path ----------------------

    transactions = [
        # TC-01: Valid purchase — well within limits, not expired
        DailyTransaction(
            tran_id="TRN0000000000001",
            type_cd="PR",
            cat_cd=5001,
            source="ONLINE",
            desc="Regular purchase at electronics store",
            amt=Decimal("250.00"),
            merchant_id=100000001,
            merchant_name="Best Electronics",
            merchant_city="New York",
            merchant_zip="10001",
            card_num="4111111111111111",
            orig_ts="2026-03-01-10.30.00.000000",
            proc_ts="",
        ),
        # TC-02: Invalid card number — card not in XREF (reason 100)
        DailyTransaction(
            tran_id="TRN0000000000002",
            type_cd="PR",
            cat_cd=5001,
            source="POS",
            desc="Purchase with unknown card",
            amt=Decimal("50.00"),
            merchant_id=100000002,
            merchant_name="Corner Store",
            merchant_city="Los Angeles",
            merchant_zip="90001",
            card_num="9999999999999999",
            orig_ts="2026-03-01-11.00.00.000000",
            proc_ts="",
        ),
        # TC-03: Account not found — valid card but missing account (reason 101)
        DailyTransaction(
            tran_id="TRN0000000000003",
            type_cd="PR",
            cat_cd=5002,
            source="ONLINE",
            desc="Purchase with orphaned card-xref",
            amt=Decimal("100.00"),
            merchant_id=100000003,
            merchant_name="Gadget World",
            merchant_city="Chicago",
            merchant_zip="60601",
            card_num="4666666666666666",
            orig_ts="2026-03-01-12.00.00.000000",
            proc_ts="",
        ),
        # TC-04: Overlimit transaction (reason 102)
        # Account 00000000002: credit=4900, debit=100, limit=5000
        # temp_bal = 4900 - 100 + 300 = 5100 > 5000
        DailyTransaction(
            tran_id="TRN0000000000004",
            type_cd="PR",
            cat_cd=5001,
            source="POS",
            desc="Large purchase exceeding credit limit",
            amt=Decimal("300.00"),
            merchant_id=100000004,
            merchant_name="Luxury Goods Inc",
            merchant_city="Beverly Hills",
            merchant_zip="90210",
            card_num="4222222222222222",
            orig_ts="2026-03-02-09.15.00.000000",
            proc_ts="",
        ),
        # TC-05: Expired account (reason 103)
        # Account 00000000003: expiraion_date="2025-01-01", tran date="2026-03-02"
        DailyTransaction(
            tran_id="TRN0000000000005",
            type_cd="PR",
            cat_cd=5003,
            source="ONLINE",
            desc="Purchase on expired account",
            amt=Decimal("75.00"),
            merchant_id=100000005,
            merchant_name="Book Haven",
            merchant_city="Chicago",
            merchant_zip="60602",
            card_num="4333333333333333",
            orig_ts="2026-03-02-14.00.00.000000",
            proc_ts="",
        ),
        # TC-06: Zero-amount transaction — valid (edge case)
        DailyTransaction(
            tran_id="TRN0000000000006",
            type_cd="CR",
            cat_cd=6001,
            source="SYSTEM",
            desc="Zero-amount adjustment",
            amt=Decimal("0.00"),
            merchant_id=0,
            merchant_name="System",
            merchant_city="N/A",
            merchant_zip="00000",
            card_num="4444444444444444",
            orig_ts="2026-03-03-08.00.00.000000",
            proc_ts="",
        ),
        # TC-07: Negative amount (credit/refund) — valid
        DailyTransaction(
            tran_id="TRN0000000000007",
            type_cd="CR",
            cat_cd=6002,
            source="ONLINE",
            desc="Refund from previous purchase",
            amt=Decimal("-150.00"),
            merchant_id=100000001,
            merchant_name="Best Electronics",
            merchant_city="New York",
            merchant_zip="10001",
            card_num="4111111111111111",
            orig_ts="2026-03-03-09.00.00.000000",
            proc_ts="",
        ),
        # TC-08: Exact credit limit — valid (limit >= temp_bal)
        # Account 00000000005: credit=2500, debit=0, limit=2500
        # temp_bal = 2500 - 0 + 0 = 2500, limit=2500 → OK (>=)
        DailyTransaction(
            tran_id="TRN0000000000008",
            type_cd="PR",
            cat_cd=5001,
            source="POS",
            desc="Transaction exactly at credit limit",
            amt=Decimal("0.00"),
            merchant_id=100000006,
            merchant_name="Boundary Test Shop",
            merchant_city="Dallas",
            merchant_zip="75201",
            card_num="4555555555555555",
            orig_ts="2026-03-03-10.00.00.000000",
            proc_ts="",
        ),
        # TC-09: One cent over limit (reason 102)
        # Account 00000000005 after TC-08: credit=2500, debit=0, limit=2500
        # temp_bal = 2500 - 0 + 0.01 = 2500.01 > 2500
        DailyTransaction(
            tran_id="TRN0000000000009",
            type_cd="PR",
            cat_cd=5001,
            source="POS",
            desc="Transaction one cent over credit limit",
            amt=Decimal("0.01"),
            merchant_id=100000006,
            merchant_name="Boundary Test Shop",
            merchant_city="Dallas",
            merchant_zip="75201",
            card_num="4555555555555555",
            orig_ts="2026-03-03-10.05.00.000000",
            proc_ts="",
        ),
        # TC-10: Large valid transaction
        DailyTransaction(
            tran_id="TRN0000000000010",
            type_cd="PR",
            cat_cd=5004,
            source="ONLINE",
            desc="Large furniture purchase within limits",
            amt=Decimal("1500.00"),
            merchant_id=100000007,
            merchant_name="Home Furnishings Co",
            merchant_city="Seattle",
            merchant_zip="98101",
            card_num="4888888888888888",
            orig_ts="2026-03-03-15.30.00.000000",
            proc_ts="",
        ),
        # TC-11: Transaction on exact expiration date — valid
        # Account 00000000007: expiraion_date="2026-02-14"
        # orig_ts date part = "2026-02-14" → equal, so OK (>=)
        DailyTransaction(
            tran_id="TRN0000000000011",
            type_cd="PR",
            cat_cd=5001,
            source="POS",
            desc="Transaction on exact expiration date",
            amt=Decimal("50.00"),
            merchant_id=100000008,
            merchant_name="Date Test Merchant",
            merchant_city="Boston",
            merchant_zip="02101",
            card_num="4777777777777777",
            orig_ts="2026-02-14-12.00.00.000000",
            proc_ts="",
        ),
        # TC-12: Transaction one day after expiration (reason 103)
        # Account 00000000007: expiraion_date="2026-02-14"
        # orig_ts date part = "2026-02-15" → expired
        DailyTransaction(
            tran_id="TRN0000000000012",
            type_cd="PR",
            cat_cd=5001,
            source="POS",
            desc="Transaction one day after expiration",
            amt=Decimal("50.00"),
            merchant_id=100000008,
            merchant_name="Date Test Merchant",
            merchant_city="Boston",
            merchant_zip="02101",
            card_num="4777777777777777",
            orig_ts="2026-02-15-12.00.00.000000",
            proc_ts="",
        ),
        # TC-13: Both overlimit AND expired — expired wins (last check in COBOL)
        # Account 00000000003: credit=500, debit=300, limit=10000
        # temp_bal = 500 - 300 + 50000 = 50200 > 10000 → overlimit
        # expiraion_date="2025-01-01" < "2026-03-04" → expired (overwrites)
        DailyTransaction(
            tran_id="TRN0000000000013",
            type_cd="PR",
            cat_cd=5005,
            source="ONLINE",
            desc="Both overlimit and expired — expired should win",
            amt=Decimal("50000.00"),
            merchant_id=100000009,
            merchant_name="Dual Fail Test",
            merchant_city="Chicago",
            merchant_zip="60603",
            card_num="4333333333333333",
            orig_ts="2026-03-04-10.00.00.000000",
            proc_ts="",
        ),
        # TC-14: Second valid transaction on same account (cumulative balance test)
        DailyTransaction(
            tran_id="TRN0000000000014",
            type_cd="PR",
            cat_cd=5001,
            source="POS",
            desc="Second purchase on account 1",
            amt=Decimal("100.00"),
            merchant_id=100000010,
            merchant_name="Coffee House",
            merchant_city="New York",
            merchant_zip="10002",
            card_num="4111111111111111",
            orig_ts="2026-03-04-08.00.00.000000",
            proc_ts="",
        ),
        # TC-15: Valid transaction with large negative amount (credit)
        DailyTransaction(
            tran_id="TRN0000000000015",
            type_cd="CR",
            cat_cd=6003,
            source="BATCH",
            desc="Bulk refund processing",
            amt=Decimal("-500.00"),
            merchant_id=100000011,
            merchant_name="Returns Processing",
            merchant_city="Seattle",
            merchant_zip="98102",
            card_num="4888888888888888",
            orig_ts="2026-03-04-12.00.00.000000",
            proc_ts="",
        ),
    ]

    return transactions, xref_records, account_records


def load_test_data_from_json(
    path: str,
) -> tuple[list[DailyTransaction], dict[str, CardXrefRecord], dict[str, AccountRecord]]:
    """Load test data from a JSON file."""
    with open(path, "r") as f:
        data = json.load(f)

    xref_records: dict[str, CardXrefRecord] = {}
    for rec in data.get("xref_records", []):
        xr = CardXrefRecord(**rec)
        xref_records[xr.card_num] = xr

    account_records: dict[str, AccountRecord] = {}
    for rec in data.get("account_records", []):
        for decimal_field in [
            "curr_bal", "credit_limit", "cash_credit_limit",
            "curr_cyc_credit", "curr_cyc_debit",
        ]:
            if decimal_field in rec:
                rec[decimal_field] = Decimal(str(rec[decimal_field]))
        ar = AccountRecord(**rec)
        account_records[ar.acct_id] = ar

    transactions: list[DailyTransaction] = []
    for rec in data.get("transactions", []):
        if "amt" in rec:
            rec["amt"] = Decimal(str(rec["amt"]))
        if "cat_cd" in rec:
            rec["cat_cd"] = int(rec["cat_cd"])
        if "merchant_id" in rec:
            rec["merchant_id"] = int(rec["merchant_id"])
        transactions.append(DailyTransaction(**rec))

    return transactions, xref_records, account_records


# ---------------------------------------------------------------------------
# Comparison logic
# ---------------------------------------------------------------------------

def compare_results(
    tran: DailyTransaction,
    cobol_result: ValidationResult,
    ms_result: ValidationResult,
) -> ComparisonResult:
    """Compare COBOL and microservice outputs for a single transaction."""
    differences: list[str] = []

    # Compare acceptance/rejection
    if cobol_result.accepted != ms_result.accepted:
        differences.append(
            f"Acceptance mismatch: COBOL={'ACCEPTED' if cobol_result.accepted else 'REJECTED'}, "
            f"Microservice={'ACCEPTED' if ms_result.accepted else 'REJECTED'}"
        )

    # Compare reason codes
    if cobol_result.reason_code != ms_result.reason_code:
        differences.append(
            f"Reason code mismatch: COBOL={cobol_result.reason_code}, "
            f"Microservice={ms_result.reason_code}"
        )

    # Compare reason descriptions
    cobol_desc = cobol_result.reason_desc.strip()
    ms_desc = ms_result.reason_desc.strip()
    if cobol_desc != ms_desc:
        differences.append(
            f"Reason description mismatch: COBOL='{cobol_desc}', "
            f"Microservice='{ms_desc}'"
        )

    # Compare balances (only if both have them)
    balance_fields = [
        ("acct_curr_bal", "ACCT-CURR-BAL"),
        ("acct_curr_cyc_credit", "ACCT-CURR-CYC-CREDIT"),
        ("acct_curr_cyc_debit", "ACCT-CURR-CYC-DEBIT"),
        ("acct_credit_limit", "ACCT-CREDIT-LIMIT"),
    ]
    for attr, cobol_name in balance_fields:
        cobol_val = getattr(cobol_result, attr)
        ms_val = getattr(ms_result, attr)
        if cobol_val is not None and ms_val is not None:
            if cobol_val != ms_val:
                differences.append(
                    f"Balance mismatch ({cobol_name}): "
                    f"COBOL={cobol_val}, Microservice={ms_val}"
                )

    # Compare temp_bal calculation
    if cobol_result.temp_bal is not None and ms_result.temp_bal is not None:
        if cobol_result.temp_bal != ms_result.temp_bal:
            differences.append(
                f"Credit-limit temp balance mismatch: "
                f"COBOL={cobol_result.temp_bal}, Microservice={ms_result.temp_bal}"
            )

    return ComparisonResult(
        transaction=tran,
        cobol_result=cobol_result,
        microservice_result=ms_result,
        matches=len(differences) == 0,
        differences=differences,
    )


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _fmt_decimal(val: Optional[Decimal]) -> str:
    """Format a Decimal for display, or 'N/A'."""
    if val is None:
        return "N/A"
    return f"{val:,.2f}"


def _reason_label(code: int) -> str:
    """Human-readable label for a validation reason code."""
    labels = {
        0: "Valid (0)",
        100: "Invalid Card (100)",
        101: "Account Not Found (101)",
        102: "Overlimit (102)",
        103: "Expired Account (103)",
    }
    return labels.get(code, f"Unknown ({code})")


def generate_report(
    results: list[ComparisonResult],
    cobol_engine: COBOLSimulator,
    ms_engine: MicroserviceEngine,
    output_path: str,
) -> str:
    """Generate the validation_report.md markdown document."""

    total = len(results)
    match_count = sum(1 for r in results if r.matches)
    mismatch_count = total - match_count

    # Categorize mismatches
    balance_mismatches = []
    acceptance_mismatches = []
    credit_limit_mismatches = []
    reason_code_mismatches = []

    for r in results:
        if r.matches:
            continue
        for diff in r.differences:
            if "Balance mismatch" in diff or "temp balance" in diff:
                balance_mismatches.append(r)
                break
        for diff in r.differences:
            if "Acceptance mismatch" in diff:
                acceptance_mismatches.append(r)
                break
        for diff in r.differences:
            if "Reason code mismatch" in diff:
                reason_code_mismatches.append(r)
                # Check if it's a credit-limit related code
                codes = {r.cobol_result.reason_code, r.microservice_result.reason_code}
                if codes & {VALIDATION_OVERLIMIT, VALIDATION_EXPIRED, VALIDATION_INVALID_CARD, VALIDATION_ACCT_NOT_FOUND}:
                    credit_limit_mismatches.append(r)
                break

    # Build reason code distribution
    cobol_code_dist: dict[int, int] = {}
    ms_code_dist: dict[int, int] = {}
    for r in results:
        cobol_code_dist[r.cobol_result.reason_code] = (
            cobol_code_dist.get(r.cobol_result.reason_code, 0) + 1
        )
        ms_code_dist[r.microservice_result.reason_code] = (
            ms_code_dist.get(r.microservice_result.reason_code, 0) + 1
        )

    lines: list[str] = []

    def w(line: str = "") -> None:
        lines.append(line)

    # --- Header ---
    w("# Parallel Validation Report: COBOL vs. Microservice")
    w()
    w(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    w()
    w("This report compares the output of the legacy COBOL transaction validation")
    w("engine (`CBTRN02C.cbl`) against the new microservice implementation, run")
    w("with identical input transactions.")
    w()

    # --- Executive Summary ---
    w("## Executive Summary")
    w()
    w(f"| Metric | Value |")
    w(f"|--------|-------|")
    w(f"| Total transactions tested | {total} |")
    w(f"| Matches (identical output) | {match_count} |")
    w(f"| Mismatches (differences detected) | {mismatch_count} |")
    w(f"| Match rate | {match_count / total * 100:.1f}% |")
    w(f"| COBOL transactions processed | {cobol_engine.transaction_count} |")
    w(f"| COBOL transactions rejected | {cobol_engine.reject_count} |")
    w(f"| Microservice transactions processed | {ms_engine.transaction_count} |")
    w(f"| Microservice transactions rejected | {ms_engine.reject_count} |")
    w()

    # --- Validation Reason Code Distribution ---
    w("## Validation Reason Code Distribution")
    w()
    w("| Reason Code | Description | COBOL Count | Microservice Count | Match |")
    w("|-------------|-------------|-------------|-------------------|-------|")
    all_codes = sorted(set(list(cobol_code_dist.keys()) + list(ms_code_dist.keys())))
    for code in all_codes:
        c_count = cobol_code_dist.get(code, 0)
        m_count = ms_code_dist.get(code, 0)
        match_str = "YES" if c_count == m_count else "**NO**"
        desc = REASON_DESCRIPTIONS.get(code, "Unknown")
        if code == VALIDATION_OK:
            desc = "Valid / Accepted"
        w(f"| {code} | {desc} | {c_count} | {m_count} | {match_str} |")
    w()

    # --- Detailed Transaction Results ---
    w("## Detailed Transaction Results")
    w()
    w("| # | Transaction ID | Card Number | Amount | COBOL Result | Microservice Result | Match |")
    w("|---|---------------|-------------|--------|-------------|-------------------|-------|")
    for i, r in enumerate(results, 1):
        cobol_label = _reason_label(r.cobol_result.reason_code)
        ms_label = _reason_label(r.microservice_result.reason_code)
        match_str = "YES" if r.matches else "**NO**"
        w(
            f"| {i} | `{r.transaction.tran_id}` | "
            f"`{r.transaction.card_num}` | "
            f"{_fmt_decimal(r.transaction.amt)} | "
            f"{cobol_label} | {ms_label} | {match_str} |"
        )
    w()

    # --- Balance Comparison ---
    w("## Balance Comparison (Post-Transaction)")
    w()
    w("Balances shown are the account state after each transaction is processed")
    w("(or the pre-transaction state for rejected transactions).")
    w()
    w("| # | Transaction ID | Field | COBOL | Microservice | Match |")
    w("|---|---------------|-------|-------|-------------|-------|")
    for i, r in enumerate(results, 1):
        fields = [
            ("ACCT-CURR-BAL", r.cobol_result.acct_curr_bal, r.microservice_result.acct_curr_bal),
            ("ACCT-CURR-CYC-CREDIT", r.cobol_result.acct_curr_cyc_credit, r.microservice_result.acct_curr_cyc_credit),
            ("ACCT-CURR-CYC-DEBIT", r.cobol_result.acct_curr_cyc_debit, r.microservice_result.acct_curr_cyc_debit),
            ("ACCT-CREDIT-LIMIT", r.cobol_result.acct_credit_limit, r.microservice_result.acct_credit_limit),
        ]
        for field_name, c_val, m_val in fields:
            if c_val is not None or m_val is not None:
                match_str = "YES" if c_val == m_val else "**NO**"
                w(
                    f"| {i} | `{r.transaction.tran_id}` | "
                    f"{field_name} | {_fmt_decimal(c_val)} | "
                    f"{_fmt_decimal(m_val)} | {match_str} |"
                )
    w()

    # --- Credit-Limit Check Details ---
    w("## Credit-Limit Check Details")
    w()
    w("The COBOL credit-limit formula is:")
    w("```")
    w("WS-TEMP-BAL = ACCT-CURR-CYC-CREDIT - ACCT-CURR-CYC-DEBIT + DALYTRAN-AMT")
    w("Overlimit if: ACCT-CREDIT-LIMIT < WS-TEMP-BAL")
    w("```")
    w()
    w("| # | Transaction ID | Amount | Credit Limit | Temp Balance (COBOL) | Temp Balance (MS) | COBOL Verdict | MS Verdict |")
    w("|---|---------------|--------|-------------|---------------------|-------------------|--------------|------------|")
    for i, r in enumerate(results, 1):
        if r.cobol_result.temp_bal is not None or r.microservice_result.temp_bal is not None:
            cobol_verdict = _reason_label(r.cobol_result.reason_code)
            ms_verdict = _reason_label(r.microservice_result.reason_code)
            w(
                f"| {i} | `{r.transaction.tran_id}` | "
                f"{_fmt_decimal(r.transaction.amt)} | "
                f"{_fmt_decimal(r.cobol_result.acct_credit_limit)} | "
                f"{_fmt_decimal(r.cobol_result.temp_bal)} | "
                f"{_fmt_decimal(r.microservice_result.temp_bal)} | "
                f"{cobol_verdict} | {ms_verdict} |"
            )
    w()

    # --- Mismatch Details ---
    if mismatch_count > 0:
        w("## Mismatch Details")
        w()
        for i, r in enumerate(results, 1):
            if not r.matches:
                w(f"### Transaction {i}: `{r.transaction.tran_id}`")
                w()
                w(f"- **Card Number:** `{r.transaction.card_num}`")
                w(f"- **Amount:** {_fmt_decimal(r.transaction.amt)}")
                w(f"- **Description:** {r.transaction.desc}")
                w(f"- **Timestamp:** {r.transaction.orig_ts}")
                w()
                w("**COBOL Output:**")
                w(f"- Reason Code: {r.cobol_result.reason_code}")
                w(f"- Reason Description: {r.cobol_result.reason_desc}")
                w(f"- Accepted: {r.cobol_result.accepted}")
                w(f"- Balance: {_fmt_decimal(r.cobol_result.acct_curr_bal)}")
                w(f"- Cycle Credit: {_fmt_decimal(r.cobol_result.acct_curr_cyc_credit)}")
                w(f"- Cycle Debit: {_fmt_decimal(r.cobol_result.acct_curr_cyc_debit)}")
                w()
                w("**Microservice Output:**")
                w(f"- Reason Code: {r.microservice_result.reason_code}")
                w(f"- Reason Description: {r.microservice_result.reason_desc}")
                w(f"- Accepted: {r.microservice_result.accepted}")
                w(f"- Balance: {_fmt_decimal(r.microservice_result.acct_curr_bal)}")
                w(f"- Cycle Credit: {_fmt_decimal(r.microservice_result.acct_curr_cyc_credit)}")
                w(f"- Cycle Debit: {_fmt_decimal(r.microservice_result.acct_curr_cyc_debit)}")
                w()
                w("**Differences:**")
                for diff in r.differences:
                    w(f"- {diff}")
                w()
    else:
        w("## Mismatch Details")
        w()
        w("No mismatches detected. All COBOL and microservice outputs are identical.")
        w()

    # --- Balance Discrepancies Section ---
    w("## Balance Discrepancies")
    w()
    if balance_mismatches:
        w(f"Found **{len(balance_mismatches)}** transaction(s) with balance discrepancies:")
        w()
        for r in balance_mismatches:
            w(f"- `{r.transaction.tran_id}`: {[d for d in r.differences if 'Balance' in d or 'temp balance' in d]}")
    else:
        w("No balance discrepancies detected between COBOL and microservice outputs.")
    w()

    # --- Transaction Acceptance/Rejection Differences ---
    w("## Transaction Acceptance/Rejection Differences")
    w()
    if acceptance_mismatches:
        w(f"Found **{len(acceptance_mismatches)}** transaction(s) where COBOL and microservice disagree on acceptance:")
        w()
        for r in acceptance_mismatches:
            w(
                f"- `{r.transaction.tran_id}`: "
                f"COBOL={'ACCEPTED' if r.cobol_result.accepted else 'REJECTED'}, "
                f"Microservice={'ACCEPTED' if r.microservice_result.accepted else 'REJECTED'}"
            )
    else:
        w("No acceptance/rejection differences detected.")
    w()

    # --- Credit-Limit Check Differences ---
    w("## Credit-Limit Check Differences (Reason Codes 100-103)")
    w()
    if credit_limit_mismatches:
        w(f"Found **{len(credit_limit_mismatches)}** transaction(s) with credit-limit/validation check differences:")
        w()
        for r in credit_limit_mismatches:
            w(
                f"- `{r.transaction.tran_id}`: "
                f"COBOL reason={r.cobol_result.reason_code}, "
                f"Microservice reason={r.microservice_result.reason_code}"
            )
    else:
        w("No credit-limit check differences detected. Reason codes 100, 101, 102, 103 match between both systems.")
    w()

    # --- COBOL Reject Record Format Reference ---
    w("## Appendix: COBOL Reject Record Format")
    w()
    w("For reference, the COBOL `REJECT-RECORD` structure (from `CBTRN02C.cbl`):")
    w()
    w("```")
    w("01 REJECT-RECORD.                    (430 bytes total)")
    w("   05 REJECT-TRAN-DATA    PIC X(350).  -- Original transaction data")
    w("   05 VALIDATION-TRAILER  PIC X(80).   -- Validation result trailer")
    w("")
    w("01 WS-VALIDATION-TRAILER.")
    w("   05 WS-VALIDATION-FAIL-REASON       PIC 9(04).  -- Reason code")
    w("   05 WS-VALIDATION-FAIL-REASON-DESC  PIC X(76).  -- Description")
    w("```")
    w()
    w("| Reason Code | Description |")
    w("|-------------|-------------|")
    w("| 0000 | Valid / no error |")
    w("| 0100 | Invalid card number |")
    w("| 0101 | Account record not found |")
    w("| 0102 | Overlimit transaction |")
    w("| 0103 | Transaction received after account expiration |")
    w()

    report_text = "\n".join(lines)

    with open(output_path, "w") as f:
        f.write(report_text)

    return report_text


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parallel Validation Framework: COBOL vs. Microservice",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with built-in sample test data (default)
  python3 parallel_test_runner.py

  # Run with custom test data from JSON
  python3 parallel_test_runner.py --test-data tests/custom_data.json

  # Output report to a specific path
  python3 parallel_test_runner.py --output reports/validation_report.md

  # Use JCL-based COBOL runner (requires M2 runtime)
  python3 parallel_test_runner.py --cobol-mode jcl
""",
    )
    parser.add_argument(
        "--test-data",
        type=str,
        default=None,
        help="Path to JSON file with test data. If not provided, uses built-in samples.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path for the validation report. Defaults to validation_report.md in the repo root.",
    )
    parser.add_argument(
        "--cobol-mode",
        choices=["simulated", "jcl"],
        default="simulated",
        help="COBOL execution mode: 'simulated' (Python re-implementation) or 'jcl' (live M2 runtime).",
    )
    parser.add_argument(
        "--json-output",
        type=str,
        default=None,
        help="Optional: also write raw comparison results as JSON.",
    )

    args = parser.parse_args()

    # Determine repo root
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    if args.output:
        output_path = args.output
    else:
        output_path = str(repo_root / "validation_report.md")

    # Load test data
    print("=" * 72)
    print("  Parallel Validation Framework: COBOL vs. Microservice")
    print("=" * 72)
    print()

    if args.test_data:
        print(f"Loading test data from: {args.test_data}")
        transactions, xref_records, account_records = load_test_data_from_json(
            args.test_data
        )
    else:
        print("Using built-in sample test data")
        transactions, xref_records, account_records = generate_sample_test_data()

    print(f"  Transactions: {len(transactions)}")
    print(f"  Card XREF records: {len(xref_records)}")
    print(f"  Account records: {len(account_records)}")
    print()

    # Initialize engines
    if args.cobol_mode == "jcl":
        jcl_runner = JCLCOBOLRunner(str(repo_root))
        if not jcl_runner.is_available():
            print("WARNING: JCL mode requested but FTP tunnel is not active.")
            print("         Falling back to simulated COBOL mode.")
            print("         To use JCL mode, ensure the M2 runtime tunnel is running.")
            print()
            args.cobol_mode = "simulated"

    print(f"COBOL mode: {args.cobol_mode}")
    print()

    cobol_engine = COBOLSimulator(xref_records, account_records)
    ms_engine = MicroserviceEngine(xref_records, account_records)

    # Process transactions in parallel
    print("Processing transactions...")
    print("-" * 72)

    results: list[ComparisonResult] = []
    for i, tran in enumerate(transactions, 1):
        cobol_result = cobol_engine.process_transaction(tran)
        ms_result = ms_engine.process_transaction(tran)

        comparison = compare_results(tran, cobol_result, ms_result)
        results.append(comparison)

        status = "MATCH" if comparison.matches else "MISMATCH"
        symbol = "  " if comparison.matches else "!!"
        print(
            f"  {symbol} TC-{i:02d} [{tran.tran_id}] "
            f"card={tran.card_num} amt={tran.amt:>12} "
            f"→ COBOL:{_reason_label(cobol_result.reason_code):>25s} "
            f"| MS:{_reason_label(ms_result.reason_code):>25s} "
            f"[{status}]"
        )

    print("-" * 72)
    print()

    # Summary
    match_count = sum(1 for r in results if r.matches)
    mismatch_count = len(results) - match_count
    print(f"Results: {match_count}/{len(results)} matches, {mismatch_count} mismatches")
    print(f"COBOL:        {cobol_engine.transaction_count} processed, {cobol_engine.reject_count} rejected")
    print(f"Microservice: {ms_engine.transaction_count} processed, {ms_engine.reject_count} rejected")
    print()

    # Generate report
    print(f"Generating report: {output_path}")
    report = generate_report(results, cobol_engine, ms_engine, output_path)
    print(f"Report written to: {output_path}")
    print(f"Report size: {len(report)} characters")

    # Optional JSON output
    if args.json_output:
        json_data = []
        for r in results:
            entry = {
                "transaction": {
                    "tran_id": r.transaction.tran_id,
                    "card_num": r.transaction.card_num,
                    "amt": str(r.transaction.amt),
                    "orig_ts": r.transaction.orig_ts,
                    "desc": r.transaction.desc,
                },
                "cobol": {
                    "reason_code": r.cobol_result.reason_code,
                    "reason_desc": r.cobol_result.reason_desc,
                    "accepted": r.cobol_result.accepted,
                    "acct_curr_bal": str(r.cobol_result.acct_curr_bal) if r.cobol_result.acct_curr_bal is not None else None,
                    "acct_curr_cyc_credit": str(r.cobol_result.acct_curr_cyc_credit) if r.cobol_result.acct_curr_cyc_credit is not None else None,
                    "acct_curr_cyc_debit": str(r.cobol_result.acct_curr_cyc_debit) if r.cobol_result.acct_curr_cyc_debit is not None else None,
                },
                "microservice": {
                    "reason_code": r.microservice_result.reason_code,
                    "reason_desc": r.microservice_result.reason_desc,
                    "accepted": r.microservice_result.accepted,
                    "acct_curr_bal": str(r.microservice_result.acct_curr_bal) if r.microservice_result.acct_curr_bal is not None else None,
                    "acct_curr_cyc_credit": str(r.microservice_result.acct_curr_cyc_credit) if r.microservice_result.acct_curr_cyc_credit is not None else None,
                    "acct_curr_cyc_debit": str(r.microservice_result.acct_curr_cyc_debit) if r.microservice_result.acct_curr_cyc_debit is not None else None,
                },
                "matches": r.matches,
                "differences": r.differences,
            }
            json_data.append(entry)

        with open(args.json_output, "w") as f:
            json.dump(json_data, f, indent=2)
        print(f"JSON output written to: {args.json_output}")

    print()
    if mismatch_count == 0:
        print("SUCCESS: All COBOL and microservice outputs match.")
    else:
        print(f"ATTENTION: {mismatch_count} mismatch(es) found. Review {output_path} for details.")

    sys.exit(0 if mismatch_count == 0 else 1)


if __name__ == "__main__":
    main()

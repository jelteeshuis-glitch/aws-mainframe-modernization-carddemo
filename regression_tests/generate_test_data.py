#!/usr/bin/env python3
"""
Generate fixed-width flat file test data for CBTRN02C regression tests.

Record layouts (from copybooks in app/cpy/):
  DALYTRAN-RECORD (CVTRA06Y): 350 bytes
  TRAN-RECORD     (CVTRA05Y): 350 bytes (same layout)
  CARD-XREF-RECORD(CVACT03Y): 50 bytes
  ACCOUNT-RECORD  (CVACT01Y): 300 bytes
  TRAN-CAT-BAL    (CVTRA01Y): 50 bytes
  REJECT-RECORD:              430 bytes (350 + 80 trailer)

GnuCOBOL ASCII sign overpunch (trailing):
  Positive: last digit stays '0'-'9'
  Negative: last digit 0->'p', 1->'q', ..., 9->'y'
"""

import os
import sys

# ---------------------------------------------------------------------------
# COBOL field formatters
# ---------------------------------------------------------------------------

def pic_x(value, length):
    """PIC X(length) - left-justified, space-padded."""
    return value.ljust(length)[:length]


def pic_9(value, length):
    """PIC 9(length) - unsigned numeric, zero-padded."""
    return str(int(value)).zfill(length)[-length:]


def pic_s9v(value, int_digits, dec_digits=2):
    """PIC S9(int_digits)V9(dec_digits) with trailing sign overpunch."""
    total = int_digits + dec_digits
    abs_val = abs(value)
    int_val = round(abs_val * (10 ** dec_digits))
    digits = str(int_val).zfill(total)[-total:]
    if value < 0:
        last = int(digits[-1])
        return digits[:-1] + chr(ord('p') + last)
    return digits


# ---------------------------------------------------------------------------
# Record builders
# ---------------------------------------------------------------------------

def make_dalytran(tran_id, type_cd, cat_cd, source, desc, amt,
                  merchant_id, merchant_name, merchant_city,
                  merchant_zip, card_num, orig_ts, proc_ts=''):
    """Build a 350-byte DALYTRAN record."""
    r = ''
    r += pic_x(tran_id, 16)            # DALYTRAN-ID
    r += pic_x(type_cd, 2)             # DALYTRAN-TYPE-CD
    r += pic_9(cat_cd, 4)              # DALYTRAN-CAT-CD
    r += pic_x(source, 10)             # DALYTRAN-SOURCE
    r += pic_x(desc, 100)              # DALYTRAN-DESC
    r += pic_s9v(amt, 9, 2)            # DALYTRAN-AMT  S9(09)V99
    r += pic_9(merchant_id, 9)         # DALYTRAN-MERCHANT-ID
    r += pic_x(merchant_name, 50)      # DALYTRAN-MERCHANT-NAME
    r += pic_x(merchant_city, 50)      # DALYTRAN-MERCHANT-CITY
    r += pic_x(merchant_zip, 10)       # DALYTRAN-MERCHANT-ZIP
    r += pic_x(card_num, 16)           # DALYTRAN-CARD-NUM
    r += pic_x(orig_ts, 26)            # DALYTRAN-ORIG-TS
    r += pic_x(proc_ts, 26)            # DALYTRAN-PROC-TS
    r += pic_x('', 20)                 # FILLER
    assert len(r) == 350, f"DALYTRAN len={len(r)}"
    return r


def make_xref(card_num, cust_id, acct_id):
    """Build a 50-byte CARD-XREF-RECORD."""
    r = ''
    r += pic_x(card_num, 16)           # XREF-CARD-NUM
    r += pic_9(cust_id, 9)             # XREF-CUST-ID
    r += pic_9(acct_id, 11)            # XREF-ACCT-ID
    r += pic_x('', 14)                 # FILLER
    assert len(r) == 50, f"XREF len={len(r)}"
    return r


def make_account(acct_id, active, curr_bal, credit_limit, cash_limit,
                 open_date, expiry_date, reissue_date,
                 cyc_credit, cyc_debit, addr_zip, group_id):
    """Build a 300-byte ACCOUNT-RECORD."""
    r = ''
    r += pic_9(acct_id, 11)            # ACCT-ID
    r += pic_x(active, 1)              # ACCT-ACTIVE-STATUS
    r += pic_s9v(curr_bal, 10, 2)      # ACCT-CURR-BAL        S9(10)V99
    r += pic_s9v(credit_limit, 10, 2)  # ACCT-CREDIT-LIMIT    S9(10)V99
    r += pic_s9v(cash_limit, 10, 2)    # ACCT-CASH-CREDIT-LIMIT S9(10)V99
    r += pic_x(open_date, 10)          # ACCT-OPEN-DATE
    r += pic_x(expiry_date, 10)        # ACCT-EXPIRAION-DATE
    r += pic_x(reissue_date, 10)       # ACCT-REISSUE-DATE
    r += pic_s9v(cyc_credit, 10, 2)    # ACCT-CURR-CYC-CREDIT S9(10)V99
    r += pic_s9v(cyc_debit, 10, 2)     # ACCT-CURR-CYC-DEBIT  S9(10)V99
    r += pic_x(addr_zip, 10)           # ACCT-ADDR-ZIP
    r += pic_x(group_id, 10)           # ACCT-GROUP-ID
    r += pic_x('', 178)                # FILLER
    assert len(r) == 300, f"ACCOUNT len={len(r)}"
    return r


def make_tcatbal(acct_id, type_cd, cat_cd, balance):
    """Build a 50-byte TRAN-CAT-BAL-RECORD."""
    r = ''
    r += pic_9(acct_id, 11)            # TRANCAT-ACCT-ID
    r += pic_x(type_cd, 2)             # TRANCAT-TYPE-CD
    r += pic_9(cat_cd, 4)              # TRANCAT-CD
    r += pic_s9v(balance, 9, 2)        # TRAN-CAT-BAL  S9(09)V99
    r += pic_x('', 22)                 # FILLER
    assert len(r) == 50, f"TCATBAL len={len(r)}"
    return r


def make_reject(dalytran_data, reason_code, reason_desc):
    """Build a 430-byte reject record."""
    assert len(dalytran_data) == 350
    trailer = pic_9(reason_code, 4) + pic_x(reason_desc, 76)
    assert len(trailer) == 80
    return dalytran_data + trailer


def make_tran(tran_id, type_cd, cat_cd, source, desc, amt,
              merchant_id, merchant_name, merchant_city,
              merchant_zip, card_num, orig_ts, proc_ts):
    """Build a 350-byte TRAN-RECORD (same layout as DALYTRAN)."""
    return make_dalytran(tran_id, type_cd, cat_cd, source, desc, amt,
                         merchant_id, merchant_name, merchant_city,
                         merchant_zip, card_num, orig_ts, proc_ts)


# ---------------------------------------------------------------------------
# Helper to write file
# ---------------------------------------------------------------------------

def write_file(path, content):
    """Write content (string) as bytes to a file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(content.encode('ascii'))
    print(f"  wrote {path} ({len(content)} bytes)")


def write_empty(path):
    """Write an empty file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        pass
    print(f"  wrote {path} (empty)")


# ---------------------------------------------------------------------------
# Placeholder for non-deterministic proc timestamp in expected TRANFILE
# ---------------------------------------------------------------------------
PROC_TS_PLACEHOLDER = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXX'[:26]


# ---------------------------------------------------------------------------
# Common test data values
# ---------------------------------------------------------------------------
CARD1 = "4000123456789010"
CARD2 = "4000123456789020"
CARD_BAD = "9999999999999999"
ACCT1 = 12345
ACCT2 = 67890
ACCT_MISSING = 99999
CUST1 = 1
CUST2 = 2
ORIG_TS = "2025-06-15-10.30.00.000000"
ORIG_TS_DATE = "2025-06-15"  # first 10 chars of ORIG_TS


# ---------------------------------------------------------------------------
# Test case generators
# ---------------------------------------------------------------------------

def generate_tc01(base):
    """TC01: Valid debit transaction (+500.00)."""
    d = os.path.join(base, 'tc01_valid_debit')
    amt = 500.00

    dalytran = make_dalytran(
        tran_id='0000000000000001', type_cd='01', cat_cd=5000,
        source='ONLINE', desc='GROCERY STORE PURCHASE', amt=amt,
        merchant_id=123456789, merchant_name='SUPERMART',
        merchant_city='NEW YORK', merchant_zip='10001',
        card_num=CARD1, orig_ts=ORIG_TS)

    write_file(f'{d}/input_dalytran.dat', dalytran)

    write_file(f'{d}/input_xreffile.dat',
               make_xref(CARD1, CUST1, ACCT1))

    acct_in = make_account(
        ACCT1, 'Y', 1000.00, 10000.00, 5000.00,
        '2020-01-01', '2027-12-31', '2025-01-01',
        1000.00, 0.00, '10001', 'GROUP001')
    write_file(f'{d}/input_acctfile.dat', acct_in)

    write_file(f'{d}/input_tcatbalf.dat',
               make_tcatbal(ACCT1, '01', 5000, 0.00))

    # Expected: transaction posted
    # TRAN-PROC-TS is non-deterministic; use placeholder
    exp_tran = make_tran(
        tran_id='0000000000000001', type_cd='01', cat_cd=5000,
        source='ONLINE', desc='GROCERY STORE PURCHASE', amt=amt,
        merchant_id=123456789, merchant_name='SUPERMART',
        merchant_city='NEW YORK', merchant_zip='10001',
        card_num=CARD1, orig_ts=ORIG_TS, proc_ts=PROC_TS_PLACEHOLDER)
    write_file(f'{d}/expected_tranfile.dat', exp_tran)

    # Account updated: curr_bal +500, cyc_credit +500
    exp_acct = make_account(
        ACCT1, 'Y', 1500.00, 10000.00, 5000.00,
        '2020-01-01', '2027-12-31', '2025-01-01',
        1500.00, 0.00, '10001', 'GROUP001')
    write_file(f'{d}/expected_acctfile.dat', exp_acct)

    # TCATBAL updated: balance = 0 + 500 = 500
    write_file(f'{d}/expected_tcatbalf.dat',
               make_tcatbal(ACCT1, '01', 5000, 500.00))

    # No rejects
    write_empty(f'{d}/expected_dalyrejs.dat')


def generate_tc02(base):
    """TC02: Valid credit (negative amount, -200.00)."""
    d = os.path.join(base, 'tc02_valid_credit')
    amt = -200.00

    dalytran = make_dalytran(
        tran_id='0000000000000002', type_cd='01', cat_cd=5000,
        source='ONLINE', desc='PAYMENT RECEIVED', amt=amt,
        merchant_id=123456789, merchant_name='SUPERMART',
        merchant_city='NEW YORK', merchant_zip='10001',
        card_num=CARD1, orig_ts=ORIG_TS)

    write_file(f'{d}/input_dalytran.dat', dalytran)

    write_file(f'{d}/input_xreffile.dat',
               make_xref(CARD1, CUST1, ACCT1))

    acct_in = make_account(
        ACCT1, 'Y', 1000.00, 10000.00, 5000.00,
        '2020-01-01', '2027-12-31', '2025-01-01',
        1000.00, 0.00, '10001', 'GROUP001')
    write_file(f'{d}/input_acctfile.dat', acct_in)

    write_file(f'{d}/input_tcatbalf.dat',
               make_tcatbal(ACCT1, '01', 5000, 0.00))

    # Expected: transaction posted
    exp_tran = make_tran(
        tran_id='0000000000000002', type_cd='01', cat_cd=5000,
        source='ONLINE', desc='PAYMENT RECEIVED', amt=amt,
        merchant_id=123456789, merchant_name='SUPERMART',
        merchant_city='NEW YORK', merchant_zip='10001',
        card_num=CARD1, orig_ts=ORIG_TS, proc_ts=PROC_TS_PLACEHOLDER)
    write_file(f'{d}/expected_tranfile.dat', exp_tran)

    # Account updated: curr_bal = 1000+(-200) = 800
    # amt < 0 => ADD amt TO ACCT-CURR-CYC-DEBIT => debit = 0+(-200) = -200
    # cyc_credit unchanged at 1000
    exp_acct = make_account(
        ACCT1, 'Y', 800.00, 10000.00, 5000.00,
        '2020-01-01', '2027-12-31', '2025-01-01',
        1000.00, -200.00, '10001', 'GROUP001')
    write_file(f'{d}/expected_acctfile.dat', exp_acct)

    # TCATBAL: balance = 0 + (-200) = -200
    write_file(f'{d}/expected_tcatbalf.dat',
               make_tcatbal(ACCT1, '01', 5000, -200.00))

    write_empty(f'{d}/expected_dalyrejs.dat')


def generate_tc03(base):
    """TC03: Invalid card number (not in XREFFILE)."""
    d = os.path.join(base, 'tc03_invalid_card')

    dalytran = make_dalytran(
        tran_id='0000000000000003', type_cd='01', cat_cd=5000,
        source='ONLINE', desc='ATTEMPTED PURCHASE', amt=500.00,
        merchant_id=123456789, merchant_name='SUPERMART',
        merchant_city='NEW YORK', merchant_zip='10001',
        card_num=CARD_BAD, orig_ts=ORIG_TS)

    write_file(f'{d}/input_dalytran.dat', dalytran)

    # XREFFILE has a different card, not CARD_BAD
    write_file(f'{d}/input_xreffile.dat',
               make_xref(CARD1, CUST1, ACCT1))

    # ACCTFILE must exist as valid indexed file; include a record
    acct = make_account(
        ACCT1, 'Y', 1000.00, 10000.00, 5000.00,
        '2020-01-01', '2027-12-31', '2025-01-01',
        1000.00, 0.00, '10001', 'GROUP001')
    write_file(f'{d}/input_acctfile.dat', acct)

    # TCATBALF must exist; include a record
    write_file(f'{d}/input_tcatbalf.dat',
               make_tcatbal(ACCT1, '01', 5000, 0.00))

    # Expected: no posted transactions
    write_empty(f'{d}/expected_tranfile.dat')

    # ACCTFILE unchanged
    write_file(f'{d}/expected_acctfile.dat', acct)

    # TCATBALF unchanged
    write_file(f'{d}/expected_tcatbalf.dat',
               make_tcatbal(ACCT1, '01', 5000, 0.00))

    # Reject: reason 0100
    write_file(f'{d}/expected_dalyrejs.dat',
               make_reject(dalytran, 100, 'INVALID CARD NUMBER FOUND'))


def generate_tc04(base):
    """TC04: Account not found (card in XREF, account missing)."""
    d = os.path.join(base, 'tc04_account_not_found')

    dalytran = make_dalytran(
        tran_id='0000000000000004', type_cd='01', cat_cd=5000,
        source='ONLINE', desc='PURCHASE ATTEMPT', amt=500.00,
        merchant_id=123456789, merchant_name='SUPERMART',
        merchant_city='NEW YORK', merchant_zip='10001',
        card_num=CARD1, orig_ts=ORIG_TS)

    write_file(f'{d}/input_dalytran.dat', dalytran)

    # XREFFILE maps CARD1 -> ACCT_MISSING (which won't be in ACCTFILE)
    write_file(f'{d}/input_xreffile.dat',
               make_xref(CARD1, CUST1, ACCT_MISSING))

    # ACCTFILE has ACCT1 but NOT ACCT_MISSING
    acct = make_account(
        ACCT1, 'Y', 1000.00, 10000.00, 5000.00,
        '2020-01-01', '2027-12-31', '2025-01-01',
        1000.00, 0.00, '10001', 'GROUP001')
    write_file(f'{d}/input_acctfile.dat', acct)

    write_file(f'{d}/input_tcatbalf.dat',
               make_tcatbal(ACCT1, '01', 5000, 0.00))

    # Expected: no transactions posted
    write_empty(f'{d}/expected_tranfile.dat')

    # ACCTFILE unchanged
    write_file(f'{d}/expected_acctfile.dat', acct)

    # TCATBALF unchanged
    write_file(f'{d}/expected_tcatbalf.dat',
               make_tcatbal(ACCT1, '01', 5000, 0.00))

    # Reject: reason 0101
    write_file(f'{d}/expected_dalyrejs.dat',
               make_reject(dalytran, 101, 'ACCOUNT RECORD NOT FOUND'))


def generate_tc05(base):
    """TC05: Over credit limit."""
    d = os.path.join(base, 'tc05_overlimit')
    # credit_limit=10000, cyc_credit=8000, cyc_debit=0
    # amt=5000 => temp_bal = 8000 - 0 + 5000 = 13000 > 10000 => OVERLIMIT
    # Account NOT expired (2027-12-31 >= 2025-06-15) so only 0102 triggers

    dalytran = make_dalytran(
        tran_id='0000000000000005', type_cd='01', cat_cd=5000,
        source='ONLINE', desc='BIG PURCHASE', amt=5000.00,
        merchant_id=123456789, merchant_name='SUPERMART',
        merchant_city='NEW YORK', merchant_zip='10001',
        card_num=CARD1, orig_ts=ORIG_TS)

    write_file(f'{d}/input_dalytran.dat', dalytran)

    write_file(f'{d}/input_xreffile.dat',
               make_xref(CARD1, CUST1, ACCT1))

    acct = make_account(
        ACCT1, 'Y', 8000.00, 10000.00, 5000.00,
        '2020-01-01', '2027-12-31', '2025-01-01',
        8000.00, 0.00, '10001', 'GROUP001')
    write_file(f'{d}/input_acctfile.dat', acct)

    write_file(f'{d}/input_tcatbalf.dat',
               make_tcatbal(ACCT1, '01', 5000, 0.00))

    write_empty(f'{d}/expected_tranfile.dat')
    write_file(f'{d}/expected_acctfile.dat', acct)
    write_file(f'{d}/expected_tcatbalf.dat',
               make_tcatbal(ACCT1, '01', 5000, 0.00))

    write_file(f'{d}/expected_dalyrejs.dat',
               make_reject(dalytran, 102, 'OVERLIMIT TRANSACTION'))


def generate_tc06(base):
    """TC06: Expired account."""
    d = os.path.join(base, 'tc06_expired_account')
    # expiry = 2020-01-01, transaction date = 2025-06-15
    # 2020-01-01 < 2025-06-15 => expired => reason 0103
    # Credit limit OK: temp_bal = 1000-0+500 = 1500 <= 10000

    dalytran = make_dalytran(
        tran_id='0000000000000006', type_cd='01', cat_cd=5000,
        source='ONLINE', desc='EXPIRED ACCOUNT PURCHASE', amt=500.00,
        merchant_id=123456789, merchant_name='SUPERMART',
        merchant_city='NEW YORK', merchant_zip='10001',
        card_num=CARD1, orig_ts=ORIG_TS)

    write_file(f'{d}/input_dalytran.dat', dalytran)

    write_file(f'{d}/input_xreffile.dat',
               make_xref(CARD1, CUST1, ACCT1))

    acct = make_account(
        ACCT1, 'Y', 1000.00, 10000.00, 5000.00,
        '2020-01-01', '2020-01-01', '2019-01-01',
        1000.00, 0.00, '10001', 'GROUP001')
    write_file(f'{d}/input_acctfile.dat', acct)

    write_file(f'{d}/input_tcatbalf.dat',
               make_tcatbal(ACCT1, '01', 5000, 0.00))

    write_empty(f'{d}/expected_tranfile.dat')
    write_file(f'{d}/expected_acctfile.dat', acct)
    write_file(f'{d}/expected_tcatbalf.dat',
               make_tcatbal(ACCT1, '01', 5000, 0.00))

    write_file(f'{d}/expected_dalyrejs.dat',
               make_reject(dalytran, 103,
                           'TRANSACTION RECEIVED AFTER ACCT EXPIRATION'))


def generate_tc07(base):
    """TC07: Mixed batch - 3 transactions: valid debit, invalid card, valid credit."""
    d = os.path.join(base, 'tc07_mixed_batch')

    # Transaction 1: valid debit +500 on CARD1 -> ACCT1
    tran1 = make_dalytran(
        tran_id='0000000000000010', type_cd='01', cat_cd=5000,
        source='ONLINE', desc='VALID DEBIT PURCHASE', amt=500.00,
        merchant_id=123456789, merchant_name='SUPERMART',
        merchant_city='NEW YORK', merchant_zip='10001',
        card_num=CARD1, orig_ts=ORIG_TS)

    # Transaction 2: invalid card (CARD_BAD not in XREF)
    tran2 = make_dalytran(
        tran_id='0000000000000011', type_cd='01', cat_cd=5000,
        source='ONLINE', desc='INVALID CARD ATTEMPT', amt=300.00,
        merchant_id=987654321, merchant_name='MEGASTORE',
        merchant_city='CHICAGO', merchant_zip='60601',
        card_num=CARD_BAD, orig_ts=ORIG_TS)

    # Transaction 3: valid credit -100 on CARD2 -> ACCT2
    tran3 = make_dalytran(
        tran_id='0000000000000012', type_cd='01', cat_cd=5000,
        source='ONLINE', desc='VALID CREDIT PAYMENT', amt=-100.00,
        merchant_id=555555555, merchant_name='PAYSERVICE',
        merchant_city='LOS ANGELES', merchant_zip='90001',
        card_num=CARD2, orig_ts=ORIG_TS)

    write_file(f'{d}/input_dalytran.dat', tran1 + tran2 + tran3)

    # XREFFILE: CARD1 -> ACCT1, CARD2 -> ACCT2 (no CARD_BAD)
    write_file(f'{d}/input_xreffile.dat',
               make_xref(CARD1, CUST1, ACCT1) +
               make_xref(CARD2, CUST2, ACCT2))

    # ACCTFILE: both accounts
    acct1_in = make_account(
        ACCT1, 'Y', 1000.00, 10000.00, 5000.00,
        '2020-01-01', '2027-12-31', '2025-01-01',
        1000.00, 0.00, '10001', 'GROUP001')
    acct2_in = make_account(
        ACCT2, 'Y', 2000.00, 10000.00, 5000.00,
        '2020-01-01', '2027-12-31', '2025-01-01',
        2000.00, 0.00, '90001', 'GROUP002')
    write_file(f'{d}/input_acctfile.dat', acct1_in + acct2_in)

    # TCATBALF: empty (records will be created by the program)
    write_empty(f'{d}/input_tcatbalf.dat')

    # Expected TRANFILE: 2 posted transactions (in key order)
    # Keys: "0000000000000010" < "0000000000000012"
    exp_tran1 = make_tran(
        tran_id='0000000000000010', type_cd='01', cat_cd=5000,
        source='ONLINE', desc='VALID DEBIT PURCHASE', amt=500.00,
        merchant_id=123456789, merchant_name='SUPERMART',
        merchant_city='NEW YORK', merchant_zip='10001',
        card_num=CARD1, orig_ts=ORIG_TS, proc_ts=PROC_TS_PLACEHOLDER)
    exp_tran3 = make_tran(
        tran_id='0000000000000012', type_cd='01', cat_cd=5000,
        source='ONLINE', desc='VALID CREDIT PAYMENT', amt=-100.00,
        merchant_id=555555555, merchant_name='PAYSERVICE',
        merchant_city='LOS ANGELES', merchant_zip='90001',
        card_num=CARD2, orig_ts=ORIG_TS, proc_ts=PROC_TS_PLACEHOLDER)
    write_file(f'{d}/expected_tranfile.dat', exp_tran1 + exp_tran3)

    # Expected ACCTFILE (in key order: ACCT1=12345 < ACCT2=67890):
    # ACCT1: bal=1500, cyc_credit=1500, cyc_debit=0 (amt +500 >= 0)
    # ACCT2: bal=1900, cyc_credit=2000, cyc_debit=-100 (amt -100 < 0)
    acct1_exp = make_account(
        ACCT1, 'Y', 1500.00, 10000.00, 5000.00,
        '2020-01-01', '2027-12-31', '2025-01-01',
        1500.00, 0.00, '10001', 'GROUP001')
    acct2_exp = make_account(
        ACCT2, 'Y', 1900.00, 10000.00, 5000.00,
        '2020-01-01', '2027-12-31', '2025-01-01',
        2000.00, -100.00, '90001', 'GROUP002')
    write_file(f'{d}/expected_acctfile.dat', acct1_exp + acct2_exp)

    # Expected TCATBALF (2 new records, in key order):
    # key1: (00000012345, "01", 5000) bal=+500
    # key2: (00000067890, "01", 5000) bal=-100
    write_file(f'{d}/expected_tcatbalf.dat',
               make_tcatbal(ACCT1, '01', 5000, 500.00) +
               make_tcatbal(ACCT2, '01', 5000, -100.00))

    # Expected DALYREJS: 1 reject (tran2, reason 0100)
    write_file(f'{d}/expected_dalyrejs.dat',
               make_reject(tran2, 100, 'INVALID CARD NUMBER FOUND'))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    print(f"Generating test data in {base}")

    generate_tc01(base)
    generate_tc02(base)
    generate_tc03(base)
    generate_tc04(base)
    generate_tc05(base)
    generate_tc06(base)
    generate_tc07(base)

    print("\nDone. All test data files generated.")


if __name__ == '__main__':
    main()

#!/bin/bash
# validation_harness/run_tests.sh
# Requires: gnucobol (cobc), copybooks in app/cpy/
#
# This harness compiles CBTRN02C and helper programs, then runs each
# regression test case.  Indexed VSAM files are created from sequential
# flat-file test data using small COBOL loader/dumper utilities so that
# the golden-master data committed to the repo stays human-readable.

set -euo pipefail

# ---------------------------------------------------------------------------
# Paths (relative to repo root — the harness cd's there first)
# ---------------------------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

COBOL_SRC="app/cbl/CBTRN02C.cbl"
COPYBOOK_DIR="app/cpy"
HELPERS_DIR="validation_harness/helpers"
WORKDIR="$(mktemp -d)"
if [ "${GITHUB_ACTIONS:-}" != "true" ]; then
  trap 'rm -rf "$WORKDIR"' EXIT
fi

PASS=0; FAIL=0

# ---------------------------------------------------------------------------
# Compile main program + helpers
# ---------------------------------------------------------------------------
echo "=== Compiling CBTRN02C ==="
cobc -x -I "$COPYBOOK_DIR" -o "$WORKDIR/cbtrn02c" "$COBOL_SRC"

for helper in LOADXREF LOADACCT LOADTCAT DUMPTRAN DUMPACCT DUMPTCAT; do
  cobc -x -o "$WORKDIR/$(echo $helper | tr '[:upper:]' '[:lower:]')" \
       "$HELPERS_DIR/${helper}.cbl"
done
echo "=== Compilation complete ==="
echo ""

# ---------------------------------------------------------------------------
# mask_proc_ts  — zero out the TRAN-PROC-TS field (bytes 305-330, 26 bytes)
# in each 350-byte record so that the non-deterministic processing timestamp
# does not cause spurious diffs.
# ---------------------------------------------------------------------------
mask_proc_ts() {
  local file="$1"
  python3 -c "
import sys, pathlib
data = pathlib.Path('$file').read_bytes()
out = bytearray()
for i in range(0, len(data), 350):
    rec = bytearray(data[i:i+350])
    rec[304:330] = b'X' * 26          # TRAN-PROC-TS placeholder
    out += rec
pathlib.Path('$file').write_bytes(bytes(out))
"
}

# ---------------------------------------------------------------------------
# run_test <test-case-dir-name>
# ---------------------------------------------------------------------------
run_test() {
  local TC_NAME="$1"
  local TC_DIR="regression_tests/data/$TC_NAME"
  echo "=== Running $TC_NAME ==="

  # ---- set up a clean per-test working area inside WORKDIR ----
  local TD="$WORKDIR/$TC_NAME"
  mkdir -p "$TD"

  # ---- 1. Copy sequential input (DALYTRAN) ----
  cp "$TC_DIR/input_dalytran.dat" "$TD/DALYTRAN"

  # ---- 2. Build indexed files from sequential test data ----
  #   XREFFILE
  if [ -s "$TC_DIR/input_xreffile.dat" ]; then
    export dd_SEQXREF="$REPO_ROOT/$TC_DIR/input_xreffile.dat"
  else
    # create a tiny empty sequential file so the loader opens OK
    > "$TD/_empty_xref"
    export dd_SEQXREF="$TD/_empty_xref"
  fi
  (cd "$TD" && "$WORKDIR/loadxref")
  unset dd_SEQXREF

  #   ACCTFILE
  if [ -s "$TC_DIR/input_acctfile.dat" ]; then
    export dd_SEQACCT="$REPO_ROOT/$TC_DIR/input_acctfile.dat"
  else
    > "$TD/_empty_acct"
    export dd_SEQACCT="$TD/_empty_acct"
  fi
  (cd "$TD" && "$WORKDIR/loadacct")
  unset dd_SEQACCT

  #   TCATBALF
  if [ -s "$TC_DIR/input_tcatbalf.dat" ]; then
    export dd_SEQTCAT="$REPO_ROOT/$TC_DIR/input_tcatbalf.dat"
  else
    > "$TD/_empty_tcat"
    export dd_SEQTCAT="$TD/_empty_tcat"
  fi
  (cd "$TD" && "$WORKDIR/loadtcat")
  unset dd_SEQTCAT

  # ---- 3. Create empty outputs (program creates TRANFILE & DALYREJS) ----
  > "$TD/TRANFILE"
  > "$TD/DALYREJS"

  # ---- 4. Run CBTRN02C ----
  local RC=0
  (cd "$TD" && "$WORKDIR/cbtrn02c") || RC=$?

  # RC=4 means rejections present (expected for some tests), not a crash
  if [ $RC -ne 0 ] && [ $RC -ne 4 ]; then
    echo "  FAIL: program exited with unexpected RC=$RC"
    FAIL=$((FAIL+1))
    return
  fi

  # ---- 5. Dump indexed outputs back to sequential for comparison ----
  export dd_SEQTRAN="$TD/actual_tranfile.dat"
  # Only dump TRANFILE if it has content (non-empty indexed file)
  if [ -s "$TD/TRANFILE" ]; then
    (cd "$TD" && "$WORKDIR/dumptran") 2>/dev/null || true
  else
    > "$TD/actual_tranfile.dat"
  fi
  unset dd_SEQTRAN

  export dd_SEQACCT="$TD/actual_acctfile.dat"
  (cd "$TD" && "$WORKDIR/dumpacct")
  unset dd_SEQACCT

  export dd_SEQTCAT="$TD/actual_tcatbalf.dat"
  if [ -s "$TD/TCATBALF" ]; then
    (cd "$TD" && "$WORKDIR/dumptcat") 2>/dev/null || true
  else
    > "$TD/actual_tcatbalf.dat"
  fi
  unset dd_SEQTCAT

  # ---- 6. Mask non-deterministic TRAN-PROC-TS in both expected & actual ----
  cp "$TC_DIR/expected_tranfile.dat" "$TD/expected_tranfile.dat"
  if [ -s "$TD/expected_tranfile.dat" ]; then
    mask_proc_ts "$TD/expected_tranfile.dat"
  fi
  if [ -s "$TD/actual_tranfile.dat" ]; then
    mask_proc_ts "$TD/actual_tranfile.dat"
  fi

  # ---- 7. Compare outputs ----
  local FAILED=0

  # TRANFILE
  if ! diff -q "$TD/expected_tranfile.dat" "$TD/actual_tranfile.dat" > /dev/null 2>&1; then
    echo "  FAIL: tranfile differs from expected"
    diff "$TD/expected_tranfile.dat" "$TD/actual_tranfile.dat" | head -20 || true
    FAILED=1
  fi

  # ACCTFILE
  if ! diff -q "$TC_DIR/expected_acctfile.dat" "$TD/actual_acctfile.dat" > /dev/null 2>&1; then
    echo "  FAIL: acctfile differs from expected"
    diff <(xxd "$TC_DIR/expected_acctfile.dat") <(xxd "$TD/actual_acctfile.dat") | head -30 || true
    FAILED=1
  fi

  # TCATBALF
  if ! diff -q "$TC_DIR/expected_tcatbalf.dat" "$TD/actual_tcatbalf.dat" > /dev/null 2>&1; then
    echo "  FAIL: tcatbalf differs from expected"
    diff <(xxd "$TC_DIR/expected_tcatbalf.dat") <(xxd "$TD/actual_tcatbalf.dat") | head -30 || true
    FAILED=1
  fi

  # DALYREJS (sequential — compare directly)
  if ! diff -q "$TC_DIR/expected_dalyrejs.dat" "$TD/DALYREJS" > /dev/null 2>&1; then
    echo "  FAIL: dalyrejs differs from expected"
    diff <(xxd "$TC_DIR/expected_dalyrejs.dat") <(xxd "$TD/DALYREJS") | head -30 || true
    FAILED=1
  fi

  if [ $FAILED -eq 0 ]; then
    echo "  PASS"
    PASS=$((PASS+1))
  else
    FAIL=$((FAIL+1))
  fi
}

# ---------------------------------------------------------------------------
# Run all test cases (sorted for deterministic order)
# ---------------------------------------------------------------------------
for TC in $(ls -d regression_tests/data/tc* | sort); do
  run_test "$(basename "$TC")"
done

echo ""
echo "Results: $PASS passed, $FAIL failed"

# Copy outputs for CI artifact upload on failure
if [ "${GITHUB_ACTIONS:-}" = "true" ] && [ $FAIL -ne 0 ]; then
  mkdir -p "$REPO_ROOT/test-failure-outputs"
  cp -r "$WORKDIR"/* "$REPO_ROOT/test-failure-outputs/" 2>/dev/null || true
fi

[ $FAIL -eq 0 ] || exit 1

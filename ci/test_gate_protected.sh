#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${MATHESIS_ADJUDICATE:?the gate binary}" "${LEAN4EXPORT:?the lean4export binary}"
command -v python3 >/dev/null 2>&1 || { echo "FATAL: python3 is required to read the gate's JSON"; exit 1; }
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  PASS  $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL  $1${2:+  ($2)}"; }

reached() { python3 -c '
import json, sys
d = json.loads(open(sys.argv[1]).read().splitlines()[-1])
t = next((t for t in d["targets"] if t["decl"] == sys.argv[2]), None)
if t is None or "protected_reached" not in t:
    print("ABSENT")
else:
    r = t["protected_reached"]
    print("null" if r is None else ",".join(sorted(r)) or "none")' "$TMP/out.json" "$1"; }

expect() {
  local got; got="$(reached "$1")"
  if [ "$got" = "$2" ]; then ok "$1 reaches $2"; else bad "$1 reaches $2" "$got"; fi
}

echo "gate protected names"
echo

cp -R "$ROOT/ci/fixtures/gate-protected/." "$TMP/"
cp "${GATE_DIR:-$ROOT/backend-gate}/lean-toolchain" "$TMP/"
( cd "$TMP" && lake build Cases ) > "$TMP/build.log" 2>&1 \
  || { echo "FATAL: fixtures failed to build"; tail -20 "$TMP/build.log"; exit 1; }

TARGETS="direct wrapped flt inProof clean"
# shellcheck disable=SC2086
( cd "$TMP" && lake env "$LEAN4EXPORT" Cases -- $TARGETS ) > "$TMP/cases.export" 2> "$TMP/export.err" \
  || { echo "FATAL: export failed"; tail -5 "$TMP/export.err"; exit 1; }

# shellcheck disable=SC2086
( cd "$TMP" && env -u MATHESIS_INIT_EXPORT "$MATHESIS_ADJUDICATE" cases.export -- $TARGETS notThere ) \
  > "$TMP/out.json" 2>/dev/null || true
[ -s "$TMP/out.json" ] || { echo "FATAL: the gate produced no output"; exit 1; }

expect direct   RiemannHypothesis
expect wrapped  RiemannHypothesis
expect flt      FermatLastTheorem
expect inProof  RiemannHypothesis
expect clean    none
expect notThere null

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]

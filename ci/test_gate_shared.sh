#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATE_DIR="${GATE_DIR:-$ROOT/backend-gate}"
: "${MATHESIS_ADJUDICATE:?the gate binary}" "${LEAN4EXPORT:?the lean4export binary}"
command -v python3 >/dev/null 2>&1 || { echo "FATAL: python3 is required to read the gate's JSON"; exit 1; }
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
LIMIT=60

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  PASS  $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL  $1${2:+  ($2)}"; }

field() { python3 -c '
import json, sys
d = json.loads(open(sys.argv[1]).read().splitlines()[-1])
if sys.argv[2] == "verdict":
    print(d.get("verdict"))
else:
    t = next((t for t in d["targets"] if t["decl"] == sys.argv[2]), None)
    print("ABSENT" if t is None else ",".join(sorted(t.get("axioms_reached") or [])))' "$TMP/out.json" "$1"; }

echo "gate shared proof terms ($(tr -d '[:space:]' < "$GATE_DIR/lean-toolchain"))"
echo

cp -R "$ROOT/ci/fixtures/gate-shared/." "$TMP/"
cp "$GATE_DIR/lean-toolchain" "$TMP/"
cd "$TMP" || exit 1
lake build Shared > build.log 2>&1 \
  || { echo "FATAL: fixtures failed to build"; tail -20 build.log; exit 1; }
lake env "$LEAN4EXPORT" Shared -- sharedExists > shared.export 2> export.err \
  || { echo "FATAL: export failed"; tail -5 export.err; exit 1; }

MATHESIS_INIT_EXPORT="$GATE_DIR/init.export" "$MATHESIS_ADJUDICATE" shared.export -- sharedExists \
  > out.json 2> gate.err &
GATE=$!
for _ in $(seq "$LIMIT"); do kill -0 "$GATE" 2>/dev/null || break; sleep 1; done
if kill -0 "$GATE" 2>/dev/null; then
  kill -9 "$GATE"; wait "$GATE" 2>/dev/null
  bad "a proof that is 2^48 nodes as a tree but 48 as a graph finishes in ${LIMIT}s" "still running"
  echo; echo "  $PASS passed, $FAIL failed"; exit 1
fi
wait "$GATE"
ok "a proof that is 2^48 nodes as a tree but 48 as a graph finishes in ${LIMIT}s"
[ -s out.json ] || { echo "FATAL: the gate produced no output"; tail -5 gate.err; exit 1; }

[ "$(field verdict)" = "ADMITTED" ] && ok "it is admitted" || bad "it is admitted" "$(field verdict)"
[ "$(field sharedExists)" = "Classical.choice" ] && ok "the axiom at the bottom of the shared term is reached" \
  || bad "the axiom at the bottom of the shared term is reached" "$(field sharedExists)"

echo
echo "  $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]

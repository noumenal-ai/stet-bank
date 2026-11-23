#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${MATHESIS_ADJUDICATE:?the gate binary}" "${LEAN4EXPORT:?the lean4export binary}"
HASHES="${MATHESIS_HASHES:-$(dirname "$MATHESIS_ADJUDICATE")/mathesis-hashes}"
command -v python3 >/dev/null 2>&1 || { echo "FATAL: python3 is required to read the gate's JSON"; exit 1; }
[ -x "$HASHES" ] || { echo "FATAL: no mathesis-hashes beside the gate: $HASHES"; exit 1; }
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  PASS  $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL  $1${2:+  ($2)}"; }

field() { python3 -c '
import json, sys
lines = open(sys.argv[1]).read().splitlines()
if not lines:
    print("NO-OUTPUT"); sys.exit()
d = json.loads(lines[-1])
t = d["targets"][0]
print({"verdict": d["verdict"], "hashes": d.get("constant_hashes"),
       "redefined": t.get("redefined_constant")}[sys.argv[2]])' "$TMP/$1" "$2"; }

gate() { local out="$1" list="$2"; shift 2
  if [ -n "$list" ]; then
    ( cd "$TMP" && MATHESIS_INIT_EXPORT="${GATE_DIR:-$ROOT/backend-gate}/init.export" \
        MATHESIS_CONSTANT_HASHES="$list" "$MATHESIS_ADJUDICATE" "$@" ) > "$TMP/$out" 2> "$TMP/$out.err"
  else
    ( cd "$TMP" && MATHESIS_INIT_EXPORT="${GATE_DIR:-$ROOT/backend-gate}/init.export" \
        env -u MATHESIS_CONSTANT_HASHES "$MATHESIS_ADJUDICATE" "$@" ) > "$TMP/$out" 2> "$TMP/$out.err"
  fi
  echo $?; }

echo "gate constant hash list"
echo

if "$HASHES" --self-test > "$TMP/selftest.log" 2>&1; then ok "sha256_passes_the_nist_vectors"
else bad "sha256_passes_the_nist_vectors" "$(grep FAIL "$TMP/selftest.log" | head -1)"; fi

SHA_TOOL="$(command -v sha256sum || echo 'shasum -a 256')"
diffs=0
for n in 1 55 56 63 64 65 119 120 1000 65537; do
  head -c "$n" /dev/urandom > "$TMP/bytes"
  [ "$("$HASHES" --sha256 "$TMP/bytes")" = "$($SHA_TOOL "$TMP/bytes" | cut -d' ' -f1)" ] || diffs=$((diffs+1))
done
if [ "$diffs" -eq 0 ]; then ok "sha256_agrees_with_the_system_tool_at_every_block_boundary"
else bad "sha256_agrees_with_the_system_tool_at_every_block_boundary" "$diffs sizes differ"; fi

cp -R "$ROOT/ci/fixtures/gate-hashes/." "$TMP/"
cp "${GATE_DIR:-$ROOT/backend-gate}/lean-toolchain" "$TMP/"
( cd "$TMP" && lake build Ref Honest Cand ) > "$TMP/build.log" 2>&1 \
  || { echo "FATAL: fixtures failed to build"; tail -20 "$TMP/build.log"; exit 1; }
( cd "$TMP" && lake env "$LEAN4EXPORT" Honest -- honest ) > "$TMP/honest.export" 2>/dev/null \
  && ( cd "$TMP" && lake env "$LEAN4EXPORT" Cand -- forged ) > "$TMP/cand.export" 2>/dev/null \
  || { echo "FATAL: export failed"; exit 1; }
( cd "$TMP" && lake env "$HASHES" Ref ref.hashes 2 ) > "$TMP/hashes.log" 2>&1 \
  || { echo "FATAL: mathesis-hashes failed"; cat "$TMP/hashes.log"; exit 1; }
if grep -q $'\tBudget$' "$TMP/ref.hashes" && grep -q $'\tNat.le_succ$' "$TMP/ref.hashes"; then
  ok "the_list_names_the_modules_constants_and_its_core"
else
  bad "the_list_names_the_modules_constants_and_its_core"
fi

gate honest.json "$TMP/ref.hashes" honest.export -- honest > /dev/null
[ "$(field honest.json verdict)" = "ADMITTED" ] && ok "an_honest_proof_matches_every_listed_constant_it_reaches" \
  || bad "an_honest_proof_matches_every_listed_constant_it_reaches" "$(field honest.json verdict) $(tail -1 "$TMP/honest.json.err")"
[ "$(field honest.json hashes)" != "None" ] && ok "the_report_says_the_list_was_used" \
  || bad "the_report_says_the_list_was_used"

gate cand-nolist.json "" cand.export -- forged > /dev/null
[ "$(field cand-nolist.json verdict)" = "ADMITTED" ] && ok "without_the_list_a_redefined_constant_passes" \
  || bad "without_the_list_a_redefined_constant_passes" "$(field cand-nolist.json verdict)"

gate cand.json "$TMP/ref.hashes" cand.export -- forged > /dev/null
[ "$(field cand.json verdict)" = "REJECTED" ] && [ "$(field cand.json redefined)" = "Budget" ] \
  && ok "with_the_list_the_redefined_constant_is_named" \
  || bad "with_the_list_the_redefined_constant_is_named" "$(field cand.json verdict) $(field cand.json redefined)"

printf '# empty\n' > "$TMP/empty.hashes"
rc="$(gate empty.json "$TMP/empty.hashes" honest.export -- honest)"
[ "$rc" -ne 0 ] && [ "$(field empty.json verdict)" != "ADMITTED" ] && ok "an_empty_list_fails_closed" \
  || bad "an_empty_list_fails_closed" "exit $rc"

printf 'not-a-hash\tBudget\n' > "$TMP/bad.hashes"
rc="$(gate bad.json "$TMP/bad.hashes" honest.export -- honest)"
[ "$rc" -ne 0 ] && [ "$(field bad.json verdict)" != "ADMITTED" ] && ok "a_malformed_list_fails_closed" \
  || bad "a_malformed_list_fails_closed" "exit $rc"

rc="$(gate missing.json "$TMP/nowhere.hashes" honest.export -- honest)"
[ "$rc" -ne 0 ] && [ "$(field missing.json verdict)" != "ADMITTED" ] && ok "a_missing_list_fails_closed" \
  || bad "a_missing_list_fails_closed" "exit $rc"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]

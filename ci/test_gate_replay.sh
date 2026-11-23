#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATE_DIR="${GATE_DIR:-$ROOT/backend-gate}"
: "${MATHESIS_ADJUDICATE:?the gate binary}" "${LEAN4EXPORT:?the lean4export binary}"
command -v python3 >/dev/null 2>&1 || { echo "FATAL: python3 is required to read the gate's JSON"; exit 1; }
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  PASS  $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL  $1${2:+  ($2)}"; }

field() { python3 -c '
import json, sys
d = json.loads(open(sys.argv[1]).read().splitlines()[-1])
if sys.argv[2] == "verdict":
    print(d.get("verdict"))
elif sys.argv[2] == "accepted":
    print((d.get("replay") or {}).get("accepted"))
else:
    t = next((t for t in d["targets"] if t["decl"] == sys.argv[2]), None)
    print("ABSENT" if t is None else ",".join(sorted(t.get("axioms_reached") or [])))' "$TMP/$1" "$2"; }

echo "gate replay ($(tr -d '[:space:]' < "$GATE_DIR/lean-toolchain"))"
echo

cp -R "$ROOT/ci/fixtures/gate-replay/." "$TMP/"
cp "$GATE_DIR/lean-toolchain" "$TMP/"
( cd "$TMP" && lake build Replay ) > "$TMP/build.log" 2>&1 \
  || { echo "FATAL: fixtures failed to build"; tail -20 "$TMP/build.log"; exit 1; }

adjudicate() {
  local out="$1"; shift
  ( cd "$TMP" && lake env "$LEAN4EXPORT" Replay -- "$@" ) > "$TMP/$out.export" 2> "$TMP/$out.err" \
    || { echo "FATAL: export of $* failed"; tail -5 "$TMP/$out.err"; exit 1; }
  ( cd "$TMP" && MATHESIS_INIT_EXPORT="$GATE_DIR/init.export" "$MATHESIS_ADJUDICATE" "$out.export" -- "$@" ) \
    > "$TMP/$out.json" 2>/dev/null || true
  [ -s "$TMP/$out.json" ] || { echo "FATAL: the gate produced no output for $*"; exit 1; }
}

adjudicate quot quotLiftComputes quotSoundUsed
[ "$(field quot.json accepted)" = "True" ] && ok "a quotient proof replays through the kernel" \
  || bad "a quotient proof replays through the kernel" "$(field quot.json accepted)"
[ "$(field quot.json verdict)" = "ADMITTED" ] && ok "a quotient proof is admitted" \
  || bad "a quotient proof is admitted" "$(field quot.json verdict)"
[ "$(field quot.json quotSoundUsed)" = "Quot.sound" ] && ok "Quot.sound is the one axiom reached" \
  || bad "Quot.sound is the one axiom reached" "$(field quot.json quotSoundUsed)"

adjudicate sorry sorried
[ "$(field sorry.json verdict)" != "ADMITTED" ] && ok "a sorry proof is not admitted" \
  || bad "a sorry proof is not admitted" "$(field sorry.json verdict)"
case "$(field sorry.json sorried)" in
  *sorryAx*) ok "the verdict names sorryAx" ;;
  *)         bad "the verdict names sorryAx" "$(field sorry.json sorried)" ;;
esac

echo
echo "  $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]

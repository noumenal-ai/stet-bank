from __future__ import annotations

import gzip
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_loader = SourceFileLoader("mathesis_cli", str(ROOT / "bin" / "mathesis"))
_spec = importlib.util.spec_from_loader("mathesis_cli", _loader)
cli = importlib.util.module_from_spec(_spec)
_loader.exec_module(cli)

PASSES: list[str] = []
FAILURES: list[str] = []

RH = ["RiemannHypothesis"]
CASES = {
    "listed": (RH, RH),
    "omitted": (RH, None),
    "invented": ([], RH),
    "unwalked": (None, []),
    "neither": ([], None),
}


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASSES if ok else FAILURES).append(name if ok else f"{name}: {detail}")
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))


def record(decl: str, sha: str, names: list[str] | None) -> dict:
    r = {"accession": f"MTH.R-2026-{decl}", "export_sha256": sha, "root_decl_name": decl,
         "dictionary_id": "dict", "axioms_reached": [], "claim_accession": "MTH.C-2026-0001"}
    if names is not None:
        r["protected_names"] = names
    return r


def failures_for(decl: str) -> list[str]:
    return [f for f in cli.FAILURES if f"MTH.R-2026-{decl}" in f]


def main() -> int:
    if not cli.gate_exe(cli.DEFAULT_GATE).is_file():
        print("FATAL: build the gate first: cd backend-gate && lake build mathesis-adjudicate")
        return 1

    cache = Path(tempfile.mkdtemp())
    raw = b'{"meta":{}}\n'
    sha = hashlib.sha256(raw).hexdigest()
    with gzip.open(cache / f"{sha}.export.gz", "wb") as fh:
        fh.write(raw)
    os.environ["BANK_EXPORTS_DIR"] = str(cache)
    os.environ.pop("MATHESIS_ADJUDICATE", None)

    toolchain = cli.gate_toolchain(cli.DEFAULT_GATE)
    real_load = cli.load
    cli.load = lambda path: ([{"id": "dict", "toolchain": toolchain}]
                             if path == cli.DICTIONARY else real_load(path))
    cli.arguments = lambda: [record(decl, sha, names) for decl, (_, names) in CASES.items()]
    cli.claims = lambda: []
    cli.statement_mismatch = lambda claim, target: None

    def fake_run(cmd, cwd=None, capture_output=False, text=False, env=None):
        if cmd[:2] == ["lean", "--print-prefix"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="/sysroot\n", stderr="")
        decl = cmd[-1]
        verdict = {"verdict": "ADMITTED", "replay": {"accepted": True},
                   "targets": [{"decl": decl, "triviality": None, "axioms_reached": [],
                                "protected_reached": CASES[decl][0]}]}
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(verdict), stderr="")

    cli.subprocess.run = fake_run
    cli.FAILURES.clear()
    with redirect_stdout(io.StringIO()):
        cli.leg_rederive(None)

    check("a record listing what the proof reaches verifies", not failures_for("listed"), str(failures_for("listed")))
    check("a record omitting a protected name the proof reaches fails",
          any("protected names" in f for f in failures_for("omitted")), str(failures_for("omitted")))
    check("a record listing a protected name the proof does not reach fails",
          any("protected names" in f for f in failures_for("invented")), str(failures_for("invented")))
    check("a gate that did not walk the closure fails the record",
          any("did not report" in f for f in failures_for("unwalked")), str(failures_for("unwalked")))
    check("a record reaching no protected name needs no field", not failures_for("neither"), str(failures_for("neither")))

    print(f"\n  {len(PASSES)} passed, {len(FAILURES)} failed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())

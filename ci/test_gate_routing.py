#!/usr/bin/env python3
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


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASSES if ok else FAILURES).append(name if ok else f"{name}: {detail}")
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))


OLD = cli.gate_toolchain(cli.DEFAULT_GATE)
NEW_GATE = ROOT / "gates" / "v4.33.1"
NEW = cli.gate_toolchain(NEW_GATE)
DICTIONARY = [{"id": "dict-old", "toolchain": OLD}, {"id": "dict-new", "toolchain": NEW}]


def record(accession: str, dictionary_id: str, sha: str) -> dict:
    return {"accession": accession, "export_sha256": sha, "root_decl_name": "thm",
            "dictionary_id": dictionary_id, "axioms_reached": [], "claim_accession": "MTH.C-2026-0001"}


def main() -> int:
    for gate in (cli.DEFAULT_GATE, NEW_GATE):
        if not cli.gate_exe(gate).is_file():
            print(f"FATAL: build the gate first: cd {gate.relative_to(ROOT)} && lake build mathesis-adjudicate")
            return 1

    check("the default gate serves its own toolchain", cli.gate_for(OLD) == cli.DEFAULT_GATE)
    check("another toolchain has its own gate", cli.gate_for(NEW) == NEW_GATE, str(cli.gate_for(NEW)))

    cache = Path(tempfile.mkdtemp())
    raw = b'{"meta":{}}\n'
    sha = hashlib.sha256(raw).hexdigest()
    with gzip.open(cache / f"{sha}.export.gz", "wb") as fh:
        fh.write(raw)
    os.environ["BANK_EXPORTS_DIR"] = str(cache)
    os.environ.pop("MATHESIS_ADJUDICATE", None)
    os.environ.pop("MATHESIS_INIT_EXPORT", None)

    real_load = cli.load
    cli.load = lambda path: DICTIONARY if path == cli.DICTIONARY else real_load(path)
    cli.arguments = lambda: [record("MTH.R-2026-0001", "dict-old", sha),
                             record("MTH.R-2026-0002", "dict-new", sha),
                             record("MTH.R-2026-0003", "dict-missing", sha)]
    cli.claims = lambda: []
    cli.statement_mismatch = lambda claim, target: None

    runs: list[tuple[list[str], dict]] = []

    def fake_run(cmd, cwd=None, capture_output=False, text=False, env=None):
        if cmd[:2] == ["lean", "--print-prefix"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=f"/sysroot/{Path(cwd).name}\n", stderr="")
        runs.append((cmd, env or {}))
        verdict = {"verdict": "ADMITTED", "replay": {"accepted": True},
                   "targets": [{"decl": "thm", "triviality": None, "axioms_reached": []}]}
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(verdict), stderr="")

    cli.subprocess.run = fake_run
    cli.FAILURES.clear()
    with redirect_stdout(io.StringIO()):
        done = cli.leg_rederive(None)

    by_exe = {Path(cmd[0]): env for cmd, env in runs}
    old_env = by_exe.get(cli.gate_exe(cli.DEFAULT_GATE))
    new_env = by_exe.get(cli.gate_exe(NEW_GATE))
    check("a record of the default toolchain runs the default gate", old_env is not None, str(list(by_exe)))
    check("a record of another toolchain runs that toolchain's gate", new_env is not None, str(list(by_exe)))
    check("each gate gets its own init.export",
          bool(old_env and new_env)
          and old_env["MATHESIS_INIT_EXPORT"] == str(cli.DEFAULT_GATE / "init.export")
          and new_env["MATHESIS_INIT_EXPORT"] == str(NEW_GATE / "init.export"))
    check("each gate gets its own toolchain's sysroot",
          bool(old_env and new_env)
          and old_env["LEAN_SYSROOT"] == "/sysroot/backend-gate"
          and new_env["LEAN_SYSROOT"] == "/sysroot/v4.33.1")
    check("a record whose dictionary entry is missing fails loudly",
          any("MTH.R-2026-0003" in f and "dict-missing" in f for f in cli.FAILURES), str(cli.FAILURES))
    check("the two resolvable records were re-derived", done == 2, str(done))

    print(f"\n  {len(PASSES)} passed, {len(FAILURES)} failed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())

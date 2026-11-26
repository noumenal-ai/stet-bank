#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import io
import json
import os
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


ACC = "MTH.R-2026-6600"
HEAVY = {"peak_memory_gb": 107, "hours": 12.9}


def argument(**over) -> dict:
    a = {
        "accession": ACC, "axiom_free": False,
        "axioms_reached": ["Classical.choice", "Quot.sound", "propext"],
        "citation_name": "A. Author", "cites": [], "claim_accession": "MTH.C-2026-6600",
        "created_at": "2026-11-25T00:00:00Z", "dictionary_id": "00000000-0000-4000-8000-000000000000",
        "edge_count": 0, "export_bytes": 61570595788, "export_constants": 1484733,
        "export_sha256": "5" * 64, "libraries_used": ["Mathlib"], "login": "author", "node_count": 1,
        "private_helpers": [], "profile_id": "00000000-0000-4000-8000-000000000001",
        "replay_detail": "lean kernel accepts", "root_decl_name": "riemannHypothesis",
        "root_module": "Main", "root_pretty": "RiemannHypothesis", "source_url": None,
        "statement_identity": "pass", "submission_id": "00000000-0000-4000-8000-000000000002",
        "substrate": "lean4export",
    }
    a.update(over)
    return a


def node(name: str, root: bool) -> dict:
    return {"citable": root, "decl_name": name, "depth": 0 if root else 1, "dictionary_leaves": [],
            "is_root": root, "kind": "theorem", "pretty": name, "topo": 0 if root else 1,
            "type_sha256": ("a" if root else "b") * 64}


ROOT_NODE = node("riemannHypothesis", True)
STEP_NODE = node("step", False)
EDGE = {"used_by": "riemannHypothesis", "uses": "step", "via": "direct"}
PARTS = [{"sha256": "c" * 64, "bytes": 2_000_000_000}, {"sha256": "d" * 64, "bytes": 1_000}]



try:
    from jsonschema import Draft202012Validator

    schema = json.loads((ROOT / "schema" / "bank-manifest.v2.schema.json").read_text())
    v = Draft202012Validator({"$defs": schema["$defs"], "$ref": "#/$defs/argumentFile"})

    def errors(doc: dict) -> list[str]:
        return [e.message for e in v.iter_errors(doc)]

    full = {"argument": argument(heavy=HEAVY, export_parts=PARTS, graph_abbreviated=True),
            "nodes": [ROOT_NODE], "edges": [], "leaves": []}
    errs = errors(full)
    check("a_heavy_argument_with_parts_and_an_abbreviated_graph_validates", not errs, "; ".join(errs)[:110])

    check("heavy_without_hours_is_refused",
          bool(errors({**full, "argument": argument(heavy={"peak_memory_gb": 107})})))
    check("a_single_part_is_refused",
          bool(errors({**full, "argument": argument(export_parts=PARTS[:1])})))
    check("an_abbreviated_graph_with_a_step_is_refused",
          bool(errors({**full, "nodes": [ROOT_NODE, STEP_NODE]})))
    check("an_abbreviated_graph_with_an_edge_is_refused",
          bool(errors({**full, "edges": [EDGE]})))
    check("an_abbreviated_graph_whose_node_is_not_the_root_is_refused",
          bool(errors({**full, "nodes": [STEP_NODE]})))
    check("graph_abbreviated_false_is_refused",
          bool(errors({**full, "argument": argument(graph_abbreviated=False)})))

    stepwise = {"argument": argument(node_count=2, edge_count=1), "nodes": [ROOT_NODE, STEP_NODE],
                "edges": [EDGE], "leaves": []}
    errs = errors(stepwise)
    check("a_full_graph_without_the_flag_still_validates", not errs, "; ".join(errs)[:110])
except ImportError:
    print("\n  not exercised: the schema half, for want of `jsonschema`")



def run_rederive(only: str | None, heavy: bool) -> tuple[int, str, list[str]]:
    fetched: list[str] = []
    saved = cli.arguments, cli.dictionary_toolchains, cli.ready_gate, cli.fetch_evidence
    cli.arguments = lambda: [argument(heavy=HEAVY)]
    cli.dictionary_toolchains = lambda: {argument()["dictionary_id"]: "leanprover/lean4:v4.33.1"}
    cli.ready_gate = lambda gate, ready: (Path("/nonexistent/mathesis-adjudicate"), {})

    def fake_fetch(a: dict, cache: Path) -> str:
        fetched.append(a["accession"])
        return "stubbed: not fetched"

    cli.fetch_evidence = fake_fetch
    cli.FAILURES.clear()
    cli.HEAVY_SKIPPED.clear()
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            done = cli.leg_rederive(only, heavy)
        return done, buf.getvalue(), fetched
    finally:
        cli.arguments, cli.dictionary_toolchains, cli.ready_gate, cli.fetch_evidence = saved


done, out, fetched = run_rederive(None, False)
check("a_heavy_record_is_named_and_skipped_by_default",
      done == 0 and cli.HEAVY_SKIPPED == [ACC] and not fetched and "skip" in out and ACC in out
      and "107 GB" in out and not cli.FAILURES,
      f"done={done} skipped={cli.HEAVY_SKIPPED} fetched={fetched} out={out.strip()[:90]!r}")

buf = io.StringIO()
with redirect_stdout(buf):
    cli.leg_coverage(0, 1)
check("coverage_counts_a_skipped_heavy_record",
      not cli.FAILURES and "1 heavy not re-derived" in buf.getvalue(), buf.getvalue().strip()[:90])

cli.HEAVY_SKIPPED.clear()
with redirect_stdout(io.StringIO()):
    cli.leg_coverage(0, 1)
check("coverage_still_fails_for_a_record_neither_re_derived_nor_skipped",
      any(f.startswith("coverage") for f in cli.FAILURES), str(cli.FAILURES)[:90])

done, out, fetched = run_rederive(None, True)
check("--heavy re-derives it",
      fetched == [ACC] and not cli.HEAVY_SKIPPED and any("stubbed" in f for f in cli.FAILURES),
      f"fetched={fetched} failures={cli.FAILURES}")

done, out, fetched = run_rederive(ACC, False)
check("naming_the_record_re_derives_it",
      fetched == [ACC] and not cli.HEAVY_SKIPPED, f"fetched={fetched} skipped={cli.HEAVY_SKIPPED}")



def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


with tempfile.TemporaryDirectory() as t:
    tmp = Path(t)
    store = tmp / "store"
    store.mkdir()
    export = b"".join(f'{{"i":{i}}}\n'.encode() for i in range(50_000))
    blob = gzip.compress(export)
    cuts = [0, len(blob) // 3, 2 * len(blob) // 3, len(blob)]
    chunks = [blob[a:b] for a, b in zip(cuts, cuts[1:])]
    parts = [{"sha256": sha(c), "bytes": len(c)} for c in chunks]
    for c in chunks:
        (store / f"{sha(c)}.part").write_bytes(c)
    (store / f"{sha(export)}.export.gz").write_bytes(blob)
    os.environ["BANK_EXPORT_STORE"] = str(store)
    a = argument(export_sha256=sha(export), export_parts=parts)

    cache = tmp / "cache1"
    why = cli.fetch_evidence(a, cache)
    joined = cache / f"{sha(export)}.export.gz"
    check("parts_join_into_the_blob",
          why is None and joined.is_file() and joined.read_bytes() == blob
          and gzip.decompress(joined.read_bytes()) == export, f"why={why}")
    forged = [dict(p) for p in parts]
    forged[1]["sha256"] = "e" * 64
    (store / f"{'e' * 64}.part").write_bytes(b"not the part")
    why = cli.fetch_evidence(argument(export_sha256=sha(export), export_parts=forged), cache)
    check("a_records_own_parts_are_checked_even_when_its_blob_is_cached",
          why is not None and "e" * 64 in why, f"why={why}")

    (store / f"{parts[1]['sha256']}.part").write_bytes(chunks[1][:-1] + b"\0")
    cache = tmp / "cache2"
    why = cli.fetch_evidence(a, cache)
    check("a_tampered_part_is_refused",
          why is not None and "hashes to" in why and parts[1]["sha256"] in why
          and not (cache / f"{sha(export)}.export.gz").exists(), f"why={why}")

    (store / f"{parts[1]['sha256']}.part").unlink()
    cache = tmp / "cache3"
    why = cli.fetch_evidence(a, cache)
    check("a_missing_part_says_which", why is not None and parts[1]["sha256"] in why, f"why={why}")

    cache = tmp / "cache4"
    why = cli.fetch_evidence(argument(export_sha256=sha(export)), cache)
    check("a_whole_blob_still_fetches_as_before",
          why is None and (cache / f"{sha(export)}.export.gz").read_bytes() == blob, f"why={why}")

print()
print(f"{len(PASSES)} passed, {len(FAILURES)} failed")
sys.exit(1 if FAILURES else 0)

#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import io
import json
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
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))


ADA = "4571f84a-7314-5307-b61c-95010a1333a9"
GRACE = "9b0d7e2c-3a61-5f0e-8d6b-2f1c4e7a9b10"
ENV_A = "45c7a066-9dae-5af4-9ce6-3a2555b95cb3"
ENV_B = "f0ad5ef7-f585-5124-bec5-8531bd285168"


def profile(pid: str, login: str, owner: bool = False) -> dict:
    return {"id": pid, "login": login, "display_name": login, "citation_name": login,
            "github_user_id": 17, "github_type": "User", "kind": "person", "is_owner": owner,
            "created_at": "2026-10-06T00:00:00Z", "avatar": None}


def environment(eid: str, label: str) -> dict:
    return {"id": eid, "label": label, "toolchain": "leanprover/lean4:v4.33.1", "mathlib_rev": "",
            "flt_rev": "", "export_sha256": "", "export_bytes": 0, "export_constants": 0,
            "base_names_sha256": "", "module_roots": ["Submission"], "blueprint_url": "",
            "curation": "deposit", "max_source_bytes": 0, "max_export_bytes": 0,
            "adjudicate_image": "mathesis-adjudicate", "builder_image": "", "blueprint_labels": {}}


def relation(frm: str, to: str, by: str) -> dict:
    return {"from": frm, "kind": "generalises", "to": to, "asserted_by": by,
            "asserted_at": "2026-11-26T00:00:00Z"}


def post(n: int, arg: str) -> dict:
    return {"post_number": n, "argument_accession": arg, "claim_accession": arg.replace("R", "C", 1),
            "profile_id": ADA, "published_at": "2026-11-26T00:00:00Z"}


def write(path: Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")


def bank(tmp: Path, files: dict[str, object]) -> None:
    for rel, doc in files.items():
        write(tmp / "bank" / rel, doc)
    point_at(tmp)


def point_at(root: Path) -> None:
    b = root / "bank"
    cli.ROOT = root
    cli.CLAIMS = b / "claims"
    cli.ARGUMENTS = b / "arguments"
    cli.PROFILES = b / "profiles.json"
    cli.DICTIONARY = b / "dictionary.json"
    cli.RELATIONS = b / "relations.json"
    cli.POSTS = b / "posts.json"
    cli.TOPICS = b / "topics.json"
    cli.PEOPLE = b / "people.json"
    cli.PROFILE_DIR = b / "profiles"
    cli.DICTIONARY_DIR = b / "dictionary"
    cli.RELATION_DIR = b / "relations"


def run(leg, files: dict[str, object]) -> list[str]:
    with tempfile.TemporaryDirectory() as d:
        bank(Path(d), files)
        cli.FAILURES.clear()
        with redirect_stdout(io.StringIO()):
            leg()
        return list(cli.FAILURES)


def loaded(files: dict[str, object]) -> tuple[list, list, list]:
    with tempfile.TemporaryDirectory() as d:
        bank(Path(d), files)
        return cli.profiles(), cli.dictionaries(), cli.relations()


def claim(acc: str, pid: str) -> dict:
    return {"accession": acc, "arguments_count": 1, "profile_id": pid}


def argument(acc: str, pid: str) -> dict:
    return {"argument": {"accession": acc, "claim_accession": acc.replace("R", "C", 1),
                         "profile_id": pid}, "nodes": [], "edges": [], "leaves": []}


p, d, r = loaded({
    "profiles.json": [profile(ADA, "ada")],
    f"profiles/{GRACE}.json": profile(GRACE, "grace"),
    "dictionary.json": environment(ENV_A, "deposit@v4.31.0"),
    f"dictionary/{ENV_B}.json": environment(ENV_B, "deposit@v4.33.1"),
    "relations.json": [relation("MTH.C-2026-6500", "MTH.C-2026-6501", ADA)],
    "relations/MTH.C-2026-6502.json": [relation("MTH.C-2026-6502", "MTH.C-2026-6500", GRACE)],
})
check("profiles_come_from_the_file_and_the_folder", sorted(x["login"] for x in p) == ["ada", "grace"],
      str([x["login"] for x in p]))
check("environments_come_from_the_file_and_the_folder", sorted(x["id"] for x in d) == [ENV_A, ENV_B],
      str([x["id"] for x in d]))
check("relations_come_from_the_file_and_the_folder", sorted(x["from"] for x in r) ==
      ["MTH.C-2026-6500", "MTH.C-2026-6502"], str([x["from"] for x in r]))

f = run(cli.leg_filing, {
    "profiles.json": [profile(ADA, "ada", owner=True)],
    f"profiles/{GRACE}.json": profile(GRACE, "grace"),
    "dictionary.json": environment(ENV_A, "deposit@v4.31.0"),
    f"dictionary/{ENV_B}.json": environment(ENV_B, "deposit@v4.33.1"),
    "relations/MTH.C-2026-6502.json": [relation("MTH.C-2026-6502", "MTH.C-2026-6500", GRACE)],
    "posts.json": [post(2, "MTH.R-2026-6501"), post(1, "MTH.R-2026-6500")],
})
check("a_bank_filed_one_way_and_the_other_files_cleanly", not f, "; ".join(f))

f = run(cli.leg_filing, {f"profiles/{ADA}.json": profile(GRACE, "grace")})
check("a_profile_file_named_for_another_id_is_refused", any("not named by the id" in x for x in f), str(f))

f = run(cli.leg_filing, {f"dictionary/{ENV_A}.json": environment(ENV_B, "deposit@v4.33.1")})
check("an_environment_file_named_for_another_id_is_refused", any("not named by the id" in x for x in f),
      str(f))

f = run(cli.leg_filing, {
    "relations/MTH.C-2026-6502.json": [relation("MTH.C-2026-6503", "MTH.C-2026-6500", ADA)],
})
check("a_relation_filed_under_another_claim_is_refused", any("not from MTH.C-2026-6502" in x for x in f),
      str(f))

f = run(cli.leg_filing, {
    "profiles.json": [profile(ADA, "ada")],
    f"profiles/{ADA}.json": profile(ADA, "ada"),
})
check("a_profile_in_the_file_and_the_folder_is_refused", any(f"profile {ADA} is filed twice" in x for x in f),
      str(f))

f = run(cli.leg_filing, {
    "dictionary.json": [environment(ENV_A, "deposit@v4.31.0")],
    f"dictionary/{ENV_A}.json": environment(ENV_A, "deposit@v4.31.0"),
})
check("an_environment_in_the_file_and_the_folder_is_refused",
      any(f"environment {ENV_A} is filed twice" in x for x in f), str(f))

f = run(cli.leg_filing, {
    "profiles.json": [profile(ADA, "ada", owner=True)],
    f"profiles/{GRACE}.json": profile(GRACE, "grace", owner=True),
})
check("two_owners_across_the_file_and_the_folder_are_refused", any("each claim to own" in x for x in f),
      str(f))

f = run(cli.leg_filing, {
    "posts.json": [post(2, "MTH.R-2026-6502"), post(2, "MTH.R-2026-6501"), post(1, "MTH.R-2026-6500")],
})
check("a_post_number_listed_twice_is_refused", any("post_number 2 twice" in x for x in f), str(f))

f = run(cli.leg_filing, {"posts.json": [post(2, "MTH.R-2026-6501"), post(1, "MTH.R-2026-6501")]})
check("an_argument_posted_twice_is_refused",
      any("argument_accession MTH.R-2026-6501 twice" in x for x in f), str(f))

f = run(cli.leg_crosslinks, {
    "profiles.json": [profile(ADA, "ada")],
    f"profiles/{GRACE}.json": profile(GRACE, "grace"),
    "claims/MTH.C-2026-6501.json": claim("MTH.C-2026-6501", ADA),
    "arguments/MTH.R-2026-6501.json": argument("MTH.R-2026-6501", ADA),
    "claims/MTH.C-2026-6502.json": claim("MTH.C-2026-6502", GRACE),
    "arguments/MTH.R-2026-6502.json": argument("MTH.R-2026-6502", GRACE),
    "relations/MTH.C-2026-6502.json": [relation("MTH.C-2026-6502", "MTH.C-2026-6501", GRACE)],
})
check("a_record_whose_profile_is_in_the_folder_crosslinks", not f, "; ".join(f))

f = run(cli.leg_crosslinks, {
    "profiles.json": [profile(ADA, "ada")],
    "claims/MTH.C-2026-6502.json": claim("MTH.C-2026-6502", GRACE),
    "arguments/MTH.R-2026-6502.json": argument("MTH.R-2026-6502", GRACE),
})
check("a_record_whose_profile_is_nowhere_is_refused",
      sum(f"names profile {GRACE}" in x for x in f) == 2, str(f))

bad = profile(GRACE, "grace")
del bad["citation_name"]
f = run(cli.leg_schema, {f"profiles/{GRACE}.json": bad})
check("a_profile_file_is_held_to_the_schema", any(f"{GRACE}.json" in x for x in f), str(f))

f = run(cli.leg_schema, {"relations/MTH.C-2026-6502.json": [{"from": "MTH.C-2026-6502"}]})
check("a_relation_file_is_held_to_the_schema", any("MTH.C-2026-6502.json" in x for x in f), str(f))

point_at(ROOT)
cli.FAILURES.clear()
with redirect_stdout(io.StringIO()):
    cli.leg_filing()
    cli.leg_crosslinks()
check("the_committed_bank_files_cleanly", not cli.FAILURES, "; ".join(cli.FAILURES))

print()
print(f"{len(PASSES)} passed, {len(FAILURES)} failed")
sys.exit(1 if FAILURES else 0)

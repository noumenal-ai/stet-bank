# Stet

A record of machine-checked theorems, and the program that checks it.

Each record names a Lean 4 declaration, the axioms its proof reaches, and the sha256 of a frozen
export of the environment that built it. `bin/mathesis verify` fetches those exports, replays
each one through the Lean kernel, and requires that the axioms it finds are exactly the axioms
the record claims. Nothing here is taken on trust from a server, a build log, or this README.

The repository is deliberately dull. It stores the record and nothing else: no site, no build
system, no deployment configuration, no intake. Those live in the system that publishes the
record, which is a separate thing. If the code that *renders* a record could also decide what
a record says, "open" would not mean very much.

## Check it yourself

```sh
git clone https://github.com/noumenal-ai/stet-bank && cd stet-bank
pip install jsonschema
bin/mathesis verify
```

That builds the gate, downloads the evidence, and re-derives every record. It is honest about
what it costs the first time:

- **A Lean toolchain per gate.** `elan`, and the toolchain of each gate the record uses:
  `leanprover/lean4:v4.31.0` for `backend-gate/`, `leanprover/lean4:v4.33.1` for
  `gates/v4.33.1/`. Each pins its own dependencies in its `lake-manifest.json`. `.lake/` is not
  committed. No prebuilt binary is shipped on purpose — an opaque blob nobody can rebuild and
  compare would undercut the only claim this repository makes.
- **Downloads.** The frozen exports run to hundreds of megabytes per record uncompressed, which
  is not something git should carry. They live on the
  [`bank-exports-v1`](https://github.com/noumenal-ai/stet-bank/releases/tag/bank-exports-v1)
  release, named by their own sha256.

Fetching evidence from a release is safe because the blobs are content-addressed: the
decompressed bytes are re-hashed and compared to the manifest before the kernel is started, so a
substituted or corrupted export fails immediately rather than being replayed. Once they are
cached, point `BANK_EXPORT_STORE` at a local directory and the whole check runs with no network.

## Read it

`list`, `show` and `search` read the JSON off disk and compute the answer each time. They need
no toolchain, no network and no evidence — they work on a fresh clone with nothing built. That
is why there is no index, no generated catalogue and no committed report to fall out of step
with the data.

```sh
bin/mathesis list                    # every record: handle, declaration, axioms
bin/mathesis show <accession>        # one record in full, and the claim it discharges
bin/mathesis search shatter          # over declaration names, statements and docstrings
```

For any other shape, the manifests are plain JSON — pipe them.

## What `verify` checks

In order, and a failure of any one is a failure overall. Nothing is skipped silently: a leg that
cannot run is an error, not a pass.

| | |
|---|---|
| **schema** | every file matches `schema/bank-manifest.v2.schema.json` — the claims and arguments, and the six sidecars that say who wrote a record, what built it, and where it sits in the reading order |
| **crosslinks** | every argument names a claim that exists, every relation names two that do and a profile that does, and every topic a claim is filed under is one that exists |
| **dependencies** | a declaration name the record publishes means **one** statement: an argument's root carries the statement digest of the claim it discharges, and any step naming another claim's declaration carries that claim's digest too |
| **coverage** | the number re-derived, plus the heavy records named as skipped, equals the number present — "31 of 32 clean" must not print as "clean" |
| **re-derivation** | fetch `<export_sha256>.export.gz` (or its `export_parts`, each checked against its own sha256 and joined in order), check the decompressed bytes against that sha256, replay through `mathesis-adjudicate`, and require ADMITTED, an accepted replay, no triviality flag, **exactly** the axioms the manifest claims, and **exactly** the protected names it claims (below) |

The last is the one that matters, and `backend-gate/` is the source to read. The first four
catch a manifest that lies about its own shape or about what else exists; the last catches one
that lies about mathematics.

**Heavy records.** A record carrying `heavy` states what re-deriving it costs: the Riemann
Hypothesis export took 12.9 hours and 106 GB on one core. `verify` names such a record and skips
it unless asked, and says so in the coverage line and at the end of the run;
`bin/mathesis verify --heavy`, or `verify <accession>`, re-derives it like any other. Its
evidence may be stored as `export_parts`, because a release asset is capped at 2 GiB, and its
graph may be abbreviated to the root alone (`graph_abbreviated`) when the proof has too many
steps to publish one by one.

**Dependencies are derived, never stored.** Where an argument's graph contains another claim's
root declaration under that claim's statement digest, the argument depends on it, and
`mathesis show` says so — computed each time from the graphs. Nothing writes it into a file. The
hand-kept list this replaced recorded two such edges where the record holds six, which is what a
second copy of the truth tends to be worth.

**What it does not check.** That the prose describes the theorem. That the person credited
proved it. That the statement is interesting, or true of anything outside Lean.
`posts.json`, `profiles.json`, `people.json` and `dictionary.json` record who
published what; nothing here re-derives them.

**And it cannot check the relations.** `bank/relations.json` says that one result generalises
another, or shows where it stops. No kernel settles that. `verify` confirms only that a relation
points at claims that exist and carries a profile that exists; whether it is *true* is somebody's
reading of the mathematics. Each is stored with a name and a date against it, and `mathesis show`
prints them apart from everything else, because telling what was checked from what was asserted
is the whole point of reading this repository rather than taking its word.

## Layout

A deposit's pull request only adds files: its claim and argument, named by their accessions,
and — when the bank does not have them yet — its depositor's profile and its environment, named
by their ids. It edits no file another deposit could edit, so open deposits never conflict with
each other and merge in any order. Its post is not written anywhere: it is read from the argument
and numbered after the last one `posts.json` lists. `verify` refuses a profile or environment
filed twice, a file not named by the id it holds, and a post number listed twice.

| Path | Contents |
|---|---|
| `bank/claims/`, `bank/arguments/` | the record: claims, and the arguments that discharge them |
| `bank/dictionary.json`, `posts.json`, `profiles.json`, `people.json` | the rest of the record, and its authorship |
| `bank/profiles/<id>.json`, `bank/dictionary/<id>.json` | a depositor's profile, and an environment, first filed by a deposit — one file each, named by its id |
| `bank/relations.json`, `bank/relations/<claim>.json` | how a curator says two claims stand to each other — assertions, attributed and dated; a deposit's own in a file named by its claim |
| `bank/topics.json` | editorial groupings; an unclassified record is not an error |
| `bank/tools/verify-bank.sh` | the re-derivation leg on its own, if you would rather run it directly |
| `backend-gate/` | the Lean adjudicator, and `init.export`, the trusted logical core every replay is checked against |
| `backend-gate/init.export.anchor.lean`, `.README.md` | how to rebuild that reference and compare it, rather than trusting it |
| `gates/<version>/` | the same adjudicator built for another Lean toolchain: its own lakefile, `init.export` and kernel replay (`MathesisReplay.lean`); the sources are `backend-gate/`'s. A record runs the gate of its dictionary entry's toolchain |
| `backend-gate/MathesisHashes.lean`, `Mathesis/Primitive/ConstHash.lean`, `Sha256.lean` | `mathesis-hashes`: an environment's constant hash list, and the hash the gate checks it with |
| `bin/mathesis` | the program above |
| `ci/test_gate_builtins.sh`, `ci/fixtures/` | the regression test below |
| `ci/export_stats.py` | how `init.export`'s constant count is checked (`--self-test`) |
| `schema/bank-manifest.v2.schema.json` | the schema for everything in `bank/` that `verify` validates |
| `shared/reasons.v1.json` | the verdict vocabulary, for reading a rejection |

## Why the gate ships with a test that tries to break it

A candidate that redefined `Nat.gcd` once proved `2 + 2 = 5` and was **admitted**, with the
trusted export loaded. `ci/test_gate_builtins.sh` is the regression test for that, and it runs
before the record is checked in CI — a verifier that had stopped verifying would otherwise
report clean re-derivations. A repository whose pitch is "read the verifier" should ship the
test that shows it catches the thing it was written for.

Breaking it deliberately is the honest way to trust it. Flip a byte in a cached `.export.gz`
(the sha256 check fires before the kernel runs), edit one `axioms_reached` (the replay's exact-set
comparison), delete one file from `bank/arguments/` (coverage), or point a claim at an accession
that does not exist (crosslinks).

## The environment's constant hash list

A deposit can declare a constant under a name its environment already uses, as long as it does not
import the module that defines it: `def Real : Type := Unit` in a file that never imports Mathlib's
reals. The gate rejects that when the environment's genuine constant is in its trusted base. That
base was 12,683 constants, the closure of 51 hand-picked Mathlib names.

`mathesis-hashes <module> <out>` hashes every safe constant the module brings in: 766,105 for
Mathlib `fabf563`, in 87 seconds and 85 MB. Each line is a SHA-256 and a name. The hash covers what
`trustedMatches` compares, and nothing else: the kind, the number of universe parameters, the type,
a definition's value, and an inductive's or constructor's shape. It ignores binder names and
annotations, metadata and `let` non-dependence, as Lean's own expression equality does, and never
a proof.

Given `MATHESIS_CONSTANT_HASHES`, the gate hashes every constant a target reaches that the list
names, and rejects a target whose hash differs: `trusted constant redefined`. A list that is set
but empty, malformed or missing fails the gate rather than switching the check off.

`verify` does not pass a list yet. That needs each record's dictionary entry to name its list.

`ci/test_gate_hashes.sh` checks the SHA-256 against NIST's vectors and the system tool, and the
gate against a redefinition that passes without the list and is named with it.

## Extraordinary claims

A proof of a famous open problem is never published on one green check.

The gate keeps a list of protected names, `protectedNames` in `backend-gate/MathesisAdjudicate.lean`.
Today it holds Mathlib's `RiemannHypothesis` and `FermatLastTheorem`. Changing it is a pull request
against the gate, like any other change to what the gate checks.

**What is enforced:**

- The gate reports every protected name a proof reaches, through its statement or anywhere in its
  proof, as `protected_reached`. A wrapper definition does not hide one, and neither does a lemma
  buried inside the proof of something modest.
- A deposit that reaches one is never admitted automatically. It waits for a maintainer.
- The record carries the list as `protected_names`, and `verify` requires it to equal a fresh
  replay's. A record cannot leave out the claim it makes.

**What is policy, and not yet enforced by code:**

- Two named maintainers approve the merge, after a public waiting period. Who they are, and how long
  the period runs, are still to be decided.
- A second, independent kernel replays the same export on a separate machine.
- Someone outside the team reproduces the result from the published files.

**What such a record says:** only that this export typechecks, that its statement reaches the
protected definition by name, and that it uses only the three permitted axioms. Nothing about the
mathematics beyond that.

**What the list does not catch.** It matches names. The same statement written out under another
name reaches no protected name, and is treated like any other deposit. And a deposit can define its
own `RiemannHypothesis`; the list sends that to review too, where the reviewer must confirm the name
is Mathlib's own definition at the record's revision.

## Adding a record

Not through this repository. Records arrive from the deposit system, which builds a submission
in a confined container, adjudicates it with the same gate committed here, and writes the result
in. What lands here is the outcome, and the point of `bin/mathesis verify` is that you do not
have to believe any of that to check it.

## Withdrawing a record

By editing one file, in a pull request, like anything else here.

A record is withdrawn by adding three fields to its claim — `retracted_at`, `retracted_by` and
`retraction_reason` — which the schema requires together, because a record marked withdrawn
without a reason tells a reader that something is wrong and not what.

Nothing else changes. `posts.json` keeps its post, because the record *was* published;
`profiles.json` and `dictionary.json` are untouched. There is no tooling for it and that is
deliberate: it is one field on one file, it is rare, and it is a judgement rather than a
derivation.

**The record is not deleted and still verifies.** The kernel accepted that replay and nothing
about the mathematics changed, so `bin/mathesis verify` re-derives a withdrawn record exactly as
it does any other. What is withdrawn is the recommendation. Deleting it instead would fail the
crosslinks leg — the section above lists that as a way to break the verifier deliberately — and
an accession scheme whose whole point is that a citation resolves should not answer one with a
404.

`verify` lists withdrawn records at the end of a run, and names any argument with a step whose
statement digest belongs to one. Neither is a failure: failing would let a single retraction
cascade into a corpus that will not verify, which is a reason not to retract anything.

## Licence

See [LICENSE](LICENSE).

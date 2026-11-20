# Consensus design

This note describes what the leader and the validators do in `judge`, what they
must agree on, and what is checked but deliberately not compared. All names refer
to `contracts/plain_leaflet.py`.

## What runs inside the non-deterministic block

`judge` copies the needed state (both URLs, both SHA-256 values, the fact list) into
plain variables, then calls `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)`.

`leader_fn` and every validator run the same function, `_round`:

1. Fetch both entries (`gl.nondet.web.get`). HTTP 5xx or a network failure is
   `[TRANSIENT]`; any other non-200 status is `[EXTERNAL]`.
2. For each entry, in this order: size limit, SHA-256 against the value given at
   submission, strict UTF-8 decoding (no BOM, no NUL, not empty). A failure is a
   recorded **problem** (`A:HASH_MISMATCH`, `B:TOO_LARGE`, ...), not an exception.
3. Code checks every must-keep fact in each entry (whole-phrase match).
   If any fact is missing, the verdict is fixed by code and **the model is not called**.
4. Otherwise the model is asked the same narrow question twice: once with A first,
   once with B first. Each answer is `FIRST`, `SECOND`, `TIE` or `UNCLEAR` plus a quote.
   Code maps the answer back to A or B and downgrades a decisive answer to `UNCLEAR`
   if its quote is not found verbatim in the entry it favours.
5. `decide` (pure code) turns the two answers into a verdict.

After consensus, only deterministic code writes state.

## What validators must agree on

`outcomes_agree(leader, mine, a_text, b_text)`:

| Case | Rule |
|---|---|
| Either side ended with a problem | both must be problems with the identical code (`A:HASH_MISMATCH` equals `A:HASH_MISMATCH`) |
| Both judged | `rounds_agree` below |

`rounds_agree`:

| Field | Rule |
|---|---|
| `missing_a`, `missing_b` | must be equal |
| `verdict` | must be equal |
| `reason` | must be a valid reason for that verdict, **not compared** |
| `q1`, `q2` | for a `CONSISTENT` win: each must be a real quote found in the winning entry **in this validator's own copy**; otherwise they must be empty. Not compared with each other |
| shape | both results must be well formed (exact keys, sorted unique index lists, verdict/reason pairs allowed, forfeit verdicts exactly match the missing lists) |

Why quotes are not compared: two honest models quote different sentences. What
matters is that the quote is real, so each validator verifies it itself.

Why `reason` is not compared: it only distinguishes kinds of the same verdict
(for example `CONSISTENT_TIE` and `ORDER_DEPENDENT` are both `TIE`). The verdict
already carries the decision.

## Errors

| Situation | Class | Validator behaviour (`_handle_leader_error`) |
|---|---|---|
| Business rule (`NOT_OPEN`, `BAD_URL`, ...) | `[EXPECTED]` | message must match exactly |
| Source returned 4xx | `[EXTERNAL]` | message must match exactly |
| Network failure, HTTP 5xx | `[TRANSIENT]` | agree if both sides were transient |
| Model returned bad JSON or wrong keys | `[LLM_ERROR]` | disagree, so a new leader is chosen |
| Leader failed but validator succeeded | any | disagree |

If the validator's own round raises, the validator votes disagree.

## Why this is real validation and not a rubber stamp

- The validator does **not** only check the leader's output format. It repeats the
  fetch, the hash check, the fact check and both model calls, then compares the
  decision fields.
- The part a model cannot be trusted with (facts, hashes, quote existence, mapping
  of order, verdict) is code, so validators agree on it by construction. Only the
  clarity judgment depends on models.
- Position bias is controlled inside the round: the answer must survive swapping
  the order, otherwise the result is a tie, never a winner.
- Doubt never wins: `UNCLEAR`, a missing quote or a fake quote gives
  `UNDETERMINED`, which `judge` retries at most 3 times.

## What is tested, and how

Direct Mode tests (`tests/direct/test_validator.py`) call the validator path with
a recorded leader result or leader error (`run_validator`) and check, among other
things: agreement on the same outcome, disagreement on a different verdict or
different missing-fact list, a forged quote in the leader's result, a leader
result with the wrong shape, each error class above, and problem-vs-judged
mismatches. Mutation testing (198 mutants, see `docs/mutation_report.json`)
checks that the tests fail when this logic is altered.

## Limits of this evidence

- Direct Mode runs one node. Real multi-validator agreement, real model answers
  and the serialization of the closures passed to `run_nondet_unsafe` are only
  exercised in the live run (`docs/DEPLOYMENT.md`).
- If validators' models disagree on the clarity verdict (most likely on the
  `near_equal` scenario), the transaction is not accepted by that leader and a new
  round follows. The contract is built so that such disagreement is safe, not so
  that it never happens. Agreement rates over repeated runs have not been measured.

# PlainLeaflet

An Intelligent Contract for GenLayer: a small contest in which two plain-language
rewrites of a (fictional) medicine leaflet are compared, and the contract records
which one is clearer for a lay reader, or that no one can be named.

All content is fictional ("Zorlimin" does not exist). Nothing here is medical advice.

## The problem

Two people rewrite the same leaflet in plain language. Who did it better?
"Better" has two parts:

1. **Did the rewrite keep every safety-critical fact?** (dose, frequency, age limit, warning.)
   This is a checkable yes/no question.
2. **Is it clearer for a lay reader?** This is a judgment, and a single model
   asked once can be swayed by the order of the texts, by length, or by instructions
   hidden inside an entry.

## Why it needs GenLayer (the "delete GenLayer" test)

Without consensus, one party runs one model once and everyone has to trust that
answer. The part that is a judgment (part 2) is exactly the part a single
run cannot make trustworthy. Here several validators each re-run the whole round
independently (fetch both entries, check facts, ask the model in both orders) and the
transaction is accepted only if they agree on the decision fields. Remove GenLayer and
the verdict becomes one party's private model call.

Part 1 is deliberately **not** given to the model. Code does it.

## Boundary: who decides what

| Step | Owner |
|---|---|
| Fetch both entries, check SHA-256, strict UTF-8, size limit | code |
| Must-keep facts present in each entry (whole-phrase match) | code |
| Disqualify an entry that dropped a fact; the other wins by forfeit | code (model is not called) |
| Which entry is clearer, asked twice (A first, then B first) | model, one narrow question each |
| A decisive answer must quote the entry it favours | code (quote must exist verbatim in that entry) |
| Verdict from the two answers | code |
| Agreement between validators | validators (custom comparison, see `docs/CONSENSUS.md`) |

## Lifecycle

1. `open_contest(label, facts_json, prize_atto)` : an organizer lists 1 to 8 must-keep
   facts (3 to 80 characters each). At most 3 open contests per organizer.
2. `submit_entry(contest_id, url, sha256)` : the first call fills slot A, the second
   slot B. The URL must be https; the SHA-256 pins the exact text, so an entry cannot be
   swapped after submission.
3. `judge(contest_id)` : callable by the organizer or either entrant once both slots
   are filled. Runs the round under consensus.
4. `withdraw(contest_id)` : organizer only, while the contest is open.

Reads: `get_contest`, `get_result`, `winner_of`, `verdict_of`, `open_slots`, `get_stats`.

## Verdicts

| Verdict | When |
|---|---|
| `A_WINS` / `B_WINS` | both judging orders pick the same entry, with a real quote (`CONSISTENT`), or the other entry forfeited by dropping a fact |
| `TIE` | the answer depends on the order of presentation (`ORDER_DEPENDENT`), or the model finds them equal (`CONSISTENT_TIE`) |
| `DISQUALIFIED` | both entries dropped a must-keep fact |
| `UNDETERMINED` | a judging answer was unclear or had a fake quote (`JUDGE_UNCLEAR`) |

Doubt never picks a winner. `UNDETERMINED` and technical problems (fetch failure, hash
mismatch, bad encoding) are bounded retries: after 3 attempts the contest is closed
(a problem: `EXHAUSTED`; repeated doubt: recorded as `UNDETERMINED`).
The prize is recorded as state; no tokens are transferred.

## Repository layout

```
contracts/plain_leaflet.py   the contract (one file)
fixtures/                    fictional leaflet rewrites + manifest.json (hashes, expected outcomes)
scripts/make_manifest.py     regenerate manifest.json; --base-url pins raw GitHub links
scripts/print_live_commands.py   Studio field values for each live scenario
scripts/mutate.py            mutation testing on a temporary copy of the project
tests/direct/                Direct Mode tests
docs/                        DESIGN, CONSENSUS, SECURITY, DEPLOYMENT, mutation_report.json
```

## Run the checks

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest                                   # 396 tests, Direct Mode
genvm-lint check contracts/plain_leaflet.py
python scripts/make_manifest.py        # rewrites fixtures/manifest.json; must leave it unchanged
python scripts/mutate.py --summary       # recorded mutation results
```

## Six live scenarios

Each uses the same four facts and two fixture files. Expected outcomes come from
`fixtures/manifest.json`.

| Scenario | Expected verdict | Why |
|---|---|---|
| `clear_vs_dense` | `A_WINS` | clear text in slot A, dense text in slot B |
| `dense_vs_clear` | `B_WINS` | same pair, swapped slots (position-bias check) |
| `near_equal` | `TIE` | two near-identical clear texts |
| `dropped_limit` | `B_WINS`, `A_FAILED_FACTS` | A omits the 24-hour limit; model not called |
| `twelve_tablets` | `B_WINS`, `A_FAILED_FACTS` | A says "12 tablets at a time"; "2 tablets at a time" must not match inside it |
| `injection` | `B_WINS` | the dense text contains instructions aimed at the judge; they must not work |

## What has been verified, and what has not

Verified locally: 396 Direct Mode tests pass; 198 mutants of the contract were generated,
192 are caught by the tests and 6 are argued equivalent in `scripts/mutate.py`
(none unexplained); the contract was accepted by the regular Studio in a trial deploy
of an earlier version.

Live run (see `docs/DEPLOYMENT.md`): all six scenarios were run once each on the regular Studio
with 5 validators, and every one gave the expected verdict. One run per scenario does not measure
how often validators would agree on repeated runs; that has not been measured.

Not verified here: agreement rates over repeated runs, and behaviour on the newest announced
GenVM version (local tests ran on an older SDK; see `docs/DEPLOYMENT.md`).
Limitations are listed in `docs/SECURITY.md`.

## For a reviewer: fast path

1. Read the boundary table above.
2. Open `decide` and `outcomes_agree` in `contracts/plain_leaflet.py` (pure functions).
3. Open `judge` and `_round` for the consensus wiring.
4. Check `docs/DEPLOYMENT.md` for the live transactions.

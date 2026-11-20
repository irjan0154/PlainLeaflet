# PlainLeaflet: design note

## Question put to consensus

Which of two plain-language rewrites of a (fictional) patient leaflet is clearer
for a lay reader, once both are known to keep every safety-critical fact?

## Boundary

| Step | Owner |
|---|---|
| Fetch both entries, check SHA-256, strict UTF-8, size limit | code |
| Must-keep facts (dose, frequency, warnings) present in each entry | code (whole-phrase match, no `12` inside `0.12`) |
| Disqualify an entry that dropped a fact; forfeit win for the other | code (model not called) |
| Which entry is clearer, asked twice (A first, then B first) | model, one narrow question each |
| Quote check: a decisive answer must quote the entry it favours | code |
| Verdict from the two answers | code |

## Verdicts

A_WINS, B_WINS, TIE, DISQUALIFIED, UNDETERMINED.

- Both orders agree on a winner: that winner (CONSISTENT).
- The answer depends on the order, or one order finds a tie: TIE (ORDER_DEPENDENT).
- Either answer is UNCLEAR or has a fake quote: UNDETERMINED. Doubt never picks a winner.
  `judge` retries it (at most 3 attempts per contest); the last attempt is recorded.
- One entry dropped a fact: the other wins by forfeit. Both dropped: DISQUALIFIED.

## Round result (what validators compare and store)

`missing_a`, `missing_b` (fact indices), `verdict`, `reason`, `q1`, `q2`.
Must match: missing lists and verdict. Must be valid but may differ: reason
inside the verdict, quotes (each validator checks them in its own copy).

## Out of scope

No medical advice, no real leaflets, no real patient data. The prize amount is recorded as
state, not transferred.

## Decisions taken after this note was first written

- No account rules: the organizer may enter, and one author may fill both slots,
  so a single account can run every live scenario. See `docs/SECURITY.md`.
- Runner hash and the version caveat: see `docs/DEPLOYMENT.md`.
- Contract surface and lifecycle: see `README.md`. Consensus rules: `docs/CONSENSUS.md`.

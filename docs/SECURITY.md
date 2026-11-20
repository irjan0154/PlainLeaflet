# Security notes and limitations

Scope: `contracts/plain_leaflet.py`. The contract holds no funds: the prize is a
number recorded in state and nothing is transferred. It makes no calls to other
contracts and emits no messages. All data is public and fictional.

## Threats considered

| Threat | Defence in the contract | Residual risk |
|---|---|---|
| An entry is edited after submission | The SHA-256 given at submission must match the fetched bytes; mismatch is a recorded problem (`HASH_MISMATCH`), never a verdict | A participant who controls the page can change it on purpose and burn attempts (see "Griefing") |
| An entry drops a safety fact | Code checks every must-keep fact before the model is asked; a missing fact forfeits the entry, the model is not called | Presence is textual, see "What the fact check does not do" |
| A number is "found" inside another number (`2 tablets` in `12 tablets` or `0.2 tablets`) | Whole-phrase match with digit and decimal boundary rules | Only the rules described in `fact_in_text`; other notations (for example "two") do not match and count as missing |
| Instructions hidden in an entry try to steer the judge | Both texts are labelled UNTRUSTED DATA in the prompt; `defang` collapses runs of three or more `=` so an entry cannot forge the prompt delimiters; the answer must be exactly the keys `winner` and `quote`; a decisive answer needs a verbatim quote from the entry it favours | A model can still be swayed; this is reduced, not eliminated. Real model behaviour on the `injection` fixture is checked only in the live run |
| Position bias of the model | The question is asked in both orders; an answer that changes with the order gives `TIE` | Two biased answers can still agree |
| A model answer is vague or invented | `UNCLEAR`, a missing quote or a fake quote gives `UNDETERMINED`; doubt never picks a winner | Bounded retries (3) can end with `UNDETERMINED` recorded |
| A dishonest leader | Each validator repeats the whole round and compares the decision fields; a quote is checked against the validator's own copy | Real multi-validator behaviour is only verified live |
| Hostile bytes (wrong encoding, BOM, NUL, empty, huge) | Strict UTF-8, no BOM, no NUL, not empty, at most 20000 bytes per entry; each gives a recorded problem | None known |
| Unsafe URLs | Only `https`, DNS name with an alphabetic last label, port 443 only, no credentials, no whitespace or fragment, ASCII only, at most 300 characters, local-looking suffixes rejected | See "URL filter is only a filter" |
| Unbounded state or work | At most 3 open contests per organizer, at most 8 facts, bounded text sizes, at most 3 judging attempts per contest | None known |
| Unknown ids, wrong state, wrong caller | Every write checks existence, status and caller and fails with an `[EXPECTED]` error | None known |

## What the fact check does not do

The check says a phrase is present, not that the entry says it correctly.
An entry that writes "do not take 2 tablets at a time" still contains the phrase.
An entry may also paste all facts as a list and be unclear everywhere else; that
passes the code check and is left to the model. The organizer chooses the
facts, so their wording should be affirmative and exact.

## URL filter is only a filter

The contract cannot see DNS or HTTP redirects. A public-looking name can resolve
or redirect somewhere unexpected, and validators fetch the URL themselves.
Because the fetched bytes must match the pinned SHA-256, such a redirect can only
produce a problem or the exact pinned content, never different content.

## Griefing and fairness limits

- A participant who controls an entry page can alter or remove it before `judge`
  and cause a problem outcome. After 3 problems the contest is `EXHAUSTED`.
- Slots are first come, first served: the first two distinct `submit_entry` calls
  fill A and B. The organizer cannot remove an entry; the organizer can only
  `withdraw` the whole contest while it is open.
- `judge` can be called by the organizer or either entrant, so a participant
  chooses the moment.
- Uniqueness of people is not enforced. The same account may open a contest and
  fill both slots; two accounts of one person look like two people. This is
  intentional for the demo (a single account can run every scenario) and means
  the contract must not be used to distribute value in this form.

## Other limits to state plainly

- The prize is recorded, not paid.
- `reason` (for example `CONSISTENT_TIE` versus `ORDER_DEPENDENT`) and the quotes
  are validated but not compared across validators; see `docs/CONSENSUS.md`.
- The `UNDETERMINED` outcome is retried up to 3 times and only the last attempt is
  recorded as the result.
- Tests ran in Direct Mode on an older GenVM SDK than the newest announced one;
  real consensus, real model answers and agreement rates over repeated runs have
  not been measured. The live record in `docs/DEPLOYMENT.md` is the only evidence
  for those.
- Fictional content only. The contract must not be used for real leaflets or real
  medical decisions.

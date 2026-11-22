# Deployment and live record

The constructor takes no arguments. Contest ids start at 1.

## Runner version

The first line of `contracts/plain_leaflet.py` pins the runner:

```
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
```

- This hash was accepted by the regular Studio (studio.genlayer.com) in a trial
  deploy of an earlier version of this contract.
- A newer runner hash was announced for the Studio-next environment only, with a
  note that the regular Studio is not affected yet. This contract targets the
  regular Studio. If the regular Studio moves to the newer runner, the header
  (and any API changes in the migration guide) must be re-checked before deploy.
  That guide could not be read when this was written.
- Local tests ran on SDK v0.2.12 (Direct Mode) and the linter on GenVM v0.2.16.
  Neither is the newest announced version.

## Packaged contract file

SHA-256 of `contracts/plain_leaflet.py` as packaged: `6944d6f591549d87d6a529bc8ac07e2f97039b6b645d8b213a0d413738511715`

## Before the live run

1. Put the repository on GitHub (public). Commit the `fixtures/` folder.
2. Pin the fixtures to the commit and generate the live manifest:

   ```bash
   python scripts/make_manifest.py --base-url https://raw.githubusercontent.com/<user>/<repo>/<40-hex commit>/fixtures
   ```

   This writes `fixtures/manifest.live.json`. Open one raw URL in a browser and
   confirm it returns the text of the fixture (and not an HTML page).
3. Deploy the final `contracts/plain_leaflet.py` (no constructor arguments).
   Compare the code shown by the explorer with the repository file; they must be
   the same bytes. Record the file hash below.

## Running a scenario

Work on one scenario at a time. For scenario N:

```bash
python scripts/print_live_commands.py --scenario N
```

Then, in Studio, in order: `open_contest`, `submit_entry` (A), `submit_entry` (B),
`judge`, then read `get_result`. After each write, wait until the transaction
reaches a final state and check that the GenVM result is **SUCCESS**; an
accepted transaction with an error result is not a pass. Write the outcome in
the table below before starting the next scenario.

A scenario passes when `verdict` (and `reason` where listed) equals the expected
value from `fixtures/manifest.json`. If a run gives something else, record it as
it is; do not rerun until it matches. Repeating a scenario is useful, but every
run goes into the table.

## Expected outcomes

| # | Scenario | Expected verdict | Expected reason or note |
|---|---|---|---|
| 1 | `clear_vs_dense` | `A_WINS` | `CONSISTENT` |
| 2 | `dense_vs_clear` | `B_WINS` | `CONSISTENT` |
| 3 | `near_equal` | `TIE` | `CONSISTENT_TIE` or `ORDER_DEPENDENT` |
| 4 | `dropped_limit` | `B_WINS` | `A_FAILED_FACTS`, `missing_a` = [1], model not called |
| 5 | `twelve_tablets` | `B_WINS` | `A_FAILED_FACTS`, `missing_a` = [0], model not called |
| 6 | `injection` | `B_WINS` | `CONSISTENT` |

## Live record

One run per scenario, on the regular Studio (studio.genlayer.com), mode "Normal (Full Consensus)",
one account, contract file as packaged above. Each judge transaction ended `Result: SUCCESS` with
consensus history `PENDING, PROPOSING, COMMITTING, REVEALING, ACCEPTED` (no extra rounds seen).
In every run 3 or 4 of the 5 validators voted Agree and the rest showed
"Validator execution cancelled after quorum" (cancelled, not a recorded disagreement).

| Item | Value |
|---|---|
| Studio / network | studio.genlayer.com, Normal (Full Consensus) |
| Contract address | `0x5746CdD8b47B5334548900c11b2f6942F61A81C5` |
| Explorer link | https://explorer-studio.genlayer.com/address/0x5746CdD8b47B5334548900c11b2f6942F61A81C5 |
| Open in Studio | https://studio.genlayer.com/?import-contract=0x5746CdD8b47B5334548900c11b2f6942F61A81C5 |
| Contract file SHA-256 | `6944d6f591549d87d6a529bc8ac07e2f97039b6b645d8b213a0d413738511715` (explorer code was not compared byte by byte) |
| Repository commit used for fixtures | `43b99f4c7498222f46f1f7332de41d3a375afde4` (`irjan0154/PlainLeaflet`; all six raw URLs returned the expected SHA-256) |

| # | Scenario | Contest id | Verdict | Reason | `missing_a` / `missing_b` | Judge tx (prefix as seen in Studio) | Tx status when read | Matches expected |
|---|---|---|---|---|---|---|---|---|
| 1 | `clear_vs_dense` | 1 | `A_WINS` | `CONSISTENT` | [] / [] | `0xc80f685d80b1dbec2dd5055758b9cfd31f234c2fb9393eba794a39be9fc88b05` | FINALIZED, SUCCESS | yes |
| 2 | `dense_vs_clear` | 3 | `B_WINS` | `CONSISTENT` | [] / [] | `0x83deaee4...` | ACCEPTED, SUCCESS | yes |
| 3 | `near_equal` | 4 | `TIE` | `CONSISTENT_TIE` | [] / [] | `0xbd58a704...` | ACCEPTED, SUCCESS | yes |
| 4 | `dropped_limit` | 5 | `B_WINS` | `A_FAILED_FACTS` | [1] / [] | `0xb1ef75a0...` | FINALIZED, SUCCESS | yes |
| 5 | `twelve_tablets` | 6 | `B_WINS` | `A_FAILED_FACTS` | [0] / [] | `0x937b5d5e...` | FINALIZED, SUCCESS | yes |
| 6 | `injection` | 7 | `B_WINS` | `CONSISTENT` | [] / [] | `0x72a4232ea841160bbe04a204de35178a8442c85f0169fd45707cdd0e7fc838d6` | FINALIZED, SUCCESS | yes |

Models seen among the agreeing validators (as named in the Studio validator list):
scenario 1 gemma, glm, mistral; scenario 2 gemini flash lite, claude sonnet; scenario 3
gpt, gemini flash lite, grok; scenario 4 deepseek, qwen, minimax, gemini flash lite;
scenario 5 gemma, grok, claude sonnet; scenario 6 grok, deepseek, mistral, gemini flash lite.
In scenarios 4 and 5 the verdict comes from code, so the model choice does not matter there.

What the runs show: both slot orders of the clear/dense pair give the clear text (scenarios 1 and 2);
two near-identical texts give a tie; a missing fact and a "2 inside 12" near-miss are caught by code;
the text containing an instruction aimed at the judge did not win. What they do not show: a single run
per scenario says nothing about how often validators would agree on repeated runs.

Notes on things that did not go smoothly (none changed a verdict):

- At the start `open_contest` was sent three times by mistake. One call, with the facts typed without
  the surrounding brackets, did not create a contest (the contest counter was 2 afterwards). The
  duplicate, contest 2, was closed with `withdraw`. That is why the contest ids above skip 2.
- In scenario 5 one `submit_entry` was sent with a hash typed into the `url` field. The contract
  rejected it with `[EXPECTED] BAD_URL`, validators agreed on the rejection, the transaction ended
  `FINALIZED` with `Result: ERROR`, and nothing was changed in the contest. The entry was then
  submitted correctly.
- The Studio editor logged a red `gen_getContractSchemaForCode` error (GenVM v0.2.16) when the
  contract was opened. The contract deployed and its methods worked.
- The quote the model chose in scenario 1 differed from the one used in the local mock; the
  contract accepts any quote that really occurs in the favoured text.
- The final status of the judge transactions in scenarios 2 and 3 was read while `ACCEPTED`; the
  result was already readable with `get_result` (`status: JUDGED`).

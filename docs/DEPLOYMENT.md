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

Filled in after the live run. Empty until then.

| Item | Value |
|---|---|
| Studio / network | |
| Contract address | |
| Explorer link | |
| Contract file SHA-256 (matches explorer code: yes/no) | |
| Repository commit used for fixtures | |

| # | Scenario | Contest id | Verdict | Reason | `missing_a` / `missing_b` | GenVM result | Transaction link | Matches expected |
|---|---|---|---|---|---|---|---|---|
| 1 | `clear_vs_dense` | | | | | | | |
| 2 | `dense_vs_clear` | | | | | | | |
| 3 | `near_equal` | | | | | | | |
| 4 | `dropped_limit` | | | | | | | |
| 5 | `twelve_tablets` | | | | | | | |
| 6 | `injection` | | | | | | | |

Notes on runs that did not go as expected (retries, rotations, problems,
`UNDETERMINED`):

(none recorded yet)

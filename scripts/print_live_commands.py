#!/usr/bin/env python3
"""Print the values to paste into the Studio fields, one block per scenario.

    python scripts/print_live_commands.py                    # reads fixtures/manifest.live.json
    python scripts/print_live_commands.py --scenario 3

Work one scenario at a time: open, enter, enter, judge, read, write the result down.
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def render(manifest: dict, only: int = None) -> str:
    facts_json = json.dumps(manifest["facts"], ensure_ascii=False)
    out = []
    for number, scenario in enumerate(manifest["scenarios"], start=1):
        if only is not None and number != only:
            continue
        a = manifest["fixtures"][scenario["a_file"]]
        b = manifest["fixtures"][scenario["b_file"]]
        reasons = " or ".join(scenario["allowed_reasons"])
        out.append(
            "\n".join([
                "=" * 72,
                f"SCENARIO {number}: {scenario['id']}",
                f"expected: verdict {scenario['expected_verdict']} (reason {reasons})",
                f"          missing in A {scenario['missing_a']}, missing in B {scenario['missing_b']}",
                "-" * 72,
                "1. Write Methods -> open_contest   [your account]",
                f"     label      {scenario['label']}",
                f"     facts_json {facts_json}",
                f"     prize_atto {manifest['prize_atto']}",
                "   Note the contest id from Output; below it is <ID>.",
                "2. Write Methods -> submit_entry   [your account]",
                "     contest_id <ID>",
                f"     url        {a['url']}",
                f"     sha256     {a['sha256']}",
                "3. Write Methods -> submit_entry   [your account]",
                "     contest_id <ID>",
                f"     url        {b['url']}",
                f"     sha256     {b['sha256']}",
                "4. Write Methods -> judge          [your account]   (takes a few minutes)",
                "     contest_id <ID>",
                "5. Read Methods: get_contest(<ID>), get_result(<ID>), verdict_of(<ID>)",
                "   Check the transaction details show GenVM result SUCCESS, not just ACCEPTED.",
                "   Copy the result into your record now.",
            ])
        )
    if not out:
        raise SystemExit("no such scenario")
    return "\n\n".join(out) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", default=str(ROOT / "fixtures" / "manifest.live.json"))
    parser.add_argument("--scenario", type=int, help="print only this scenario number (1-based)")
    args = parser.parse_args(argv)
    path = pathlib.Path(args.manifest)
    if not path.exists():
        print(f"error: {path} not found. Upload the fixtures first, then run\n"
              "  python scripts/make_manifest.py --base-url https://raw.githubusercontent.com/<user>/<repo>/<commit>/fixtures",
              file=sys.stderr)
        return 2
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if "base_url" not in manifest:
        print("error: this is not the live manifest (no base_url)", file=sys.stderr)
        return 2
    sys.stdout.write(render(manifest, args.scenario))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

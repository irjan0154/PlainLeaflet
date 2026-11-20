"""The fixtures, the generated manifest, and every labelled scenario end to end (honest model)."""
import difflib
import importlib.util
import json
import pathlib

import pytest

from helpers import hex_of
from pure_loader import L

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"


def _load_make_manifest():
    spec = importlib.util.spec_from_file_location("make_manifest", ROOT / "scripts" / "make_manifest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MM = _load_make_manifest()
SCENARIOS = MM.SCENARIOS
TXT_FILES = sorted(p.name for p in FIXTURES.glob("zorlimin-*.txt"))   # only the files this project owns


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ============ the files themselves ============

def test_there_are_fixture_files():
    assert len(TXT_FILES) >= 6
    assert set(MM.fixture_files()) == set(TXT_FILES)       # nothing unused, nothing missing


@pytest.mark.parametrize("name", TXT_FILES)
def test_fixture_files_are_plain_lf_utf8(name):
    data = (FIXTURES / name).read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf"), "BOM"
    assert b"\r" not in data, "CRLF or CR would change the hash"
    assert b"\x00" not in data
    data.decode("utf-8")                                    # strict
    assert data.endswith(b"\n") and not data.endswith(b"\n\n"), "exactly one final newline"
    assert len(data) <= L.MAX_ENTRY_BYTES


@pytest.mark.parametrize("name", TXT_FILES)
def test_fixtures_are_marked_fictional_and_contain_no_links(name):
    text = read(name)
    assert "fictional medicine" in text.splitlines()[0].lower()
    assert "not medical advice" in text.splitlines()[0].lower()
    assert "http" not in text.lower() and "@" not in text


def test_fixtures_decode_through_the_contract_rule():
    for name in TXT_FILES:
        assert L.decode_text((FIXTURES / name).read_bytes()) == read(name)


# ============ the variants differ in exactly one line ============

@pytest.mark.parametrize("base,variant", [
    ("zorlimin-clear.txt", "zorlimin-clear-nolimit.txt"),
    ("zorlimin-clear.txt", "zorlimin-clear-twelve.txt"),
    ("zorlimin-clear.txt", "zorlimin-clear-twin.txt"),
    ("zorlimin-dense.txt", "zorlimin-dense-injection.txt"),
])
def test_each_variant_differs_from_its_base_in_one_line(base, variant):
    diff = list(difflib.ndiff(read(base).splitlines(), read(variant).splitlines()))
    removed = [d for d in diff if d.startswith("- ")]
    added = [d for d in diff if d.startswith("+ ")]
    assert len(removed) <= 1 and len(added) <= 1 and (removed or added)


def test_complete_fixtures_keep_every_fact():
    for name in ("zorlimin-clear.txt", "zorlimin-clear-twin.txt",
                 "zorlimin-dense.txt", "zorlimin-dense-injection.txt"):
        assert L.missing_facts(MM.FACTS, read(name)) == [], name


def test_twelve_tablets_is_not_mistaken_for_two():
    """'2 tablets at a time' is a substring of '12 tablets at a time'; the rule must not accept it."""
    text = read("zorlimin-clear-twelve.txt")
    assert "2 tablets at a time" in text.lower()
    assert L.missing_facts(MM.FACTS, text) == [0]


def test_dropped_limit_is_missing_only_the_limit():
    assert L.missing_facts(MM.FACTS, read("zorlimin-clear-nolimit.txt")) == [1]


# ============ the manifest ============

def test_facts_are_valid_for_the_contract():
    assert L.parse_facts(json.dumps(MM.FACTS)) == MM.FACTS


def test_manifest_is_current():
    on_disk = (FIXTURES / "manifest.json").read_text(encoding="utf-8")
    assert on_disk == MM.dumps(MM.build_manifest()), "run: python scripts/make_manifest.py"


def test_manifest_hashes_match_the_bytes():
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    for name, entry in manifest["fixtures"].items():
        data = (FIXTURES / name).read_bytes()
        assert entry["sha256"] == L.sha256_hex(data)
        assert entry["bytes"] == len(data)


def test_manifest_has_no_urls_and_the_live_one_only_pinned_raw_links():
    plain = (FIXTURES / "manifest.json").read_text(encoding="utf-8")
    assert "http" not in plain
    live_path = FIXTURES / "manifest.live.json"
    if live_path.exists():
        live = json.loads(live_path.read_text(encoding="utf-8"))
        assert MM.BASE_URL_RE.match(live["base_url"])
        for name, entry in live["fixtures"].items():
            assert entry["url"] == live["base_url"] + "/" + name
            assert L.is_valid_https_url(entry["url"])
        assert live == MM.build_manifest(base_url=live["base_url"])


def test_base_url_must_pin_a_commit():
    for bad in [
        "https://raw.githubusercontent.com/u/r/main/fixtures",
        "https://raw.githubusercontent.com/u/r/abc123/fixtures",
        "http://raw.githubusercontent.com/u/r/" + "a" * 40 + "/fixtures",
        "https://example.com/u/r/" + "a" * 40 + "/fixtures",
    ]:
        with pytest.raises(ValueError):
            MM.build_manifest(base_url=bad)
    good = "https://raw.githubusercontent.com/u/r/" + "a" * 40 + "/fixtures"
    assert MM.build_manifest(base_url=good)["base_url"] == good


def test_scenario_definitions_are_consistent():
    ids = [s["id"] for s in SCENARIOS]
    assert len(ids) == len(set(ids)) == 6
    for s in SCENARIOS:
        assert 1 <= len(s["label"]) <= L.MAX_LABEL_LEN
        assert s["expected_verdict"] in L.VERDICTS
        assert set(s["allowed_reasons"]) <= set(L.ALLOWED_REASONS[s["expected_verdict"]])
        assert s["a_file"] != s["b_file"]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_expected_missing_lists_match_the_files(scenario):
    assert L.missing_facts(MM.FACTS, read(scenario["a_file"])) == scenario["missing_a"]
    assert L.missing_facts(MM.FACTS, read(scenario["b_file"])) == scenario["missing_b"]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_the_honest_quote_is_really_in_the_file_it_favours(scenario):
    honest = scenario["honest"]
    forfeits = scenario["missing_a"] or scenario["missing_b"]
    if honest is None:
        assert forfeits, "a scenario without a model answer must be a forfeit"
        return
    assert not forfeits
    if honest["prefers"] == "TIE":
        assert honest["quote"] == ""
        return
    winner_file = scenario["a_file"] if honest["prefers"] == "A" else scenario["b_file"]
    assert L.quote_in_text(honest["quote"], read(winner_file))
    loser_file = scenario["b_file"] if honest["prefers"] == "A" else scenario["a_file"]
    assert not L.quote_in_text(honest["quote"], read(loser_file)), "the quote must identify the winner"


def test_the_injected_delimiter_is_defanged_in_the_prompt():
    prompt = L.build_prompt(read("zorlimin-dense-injection.txt"), read("zorlimin-clear.txt"))
    assert prompt.count("=====FIRST TEXT END=====") == 1


# ============ every scenario, end to end, with an honest model ============

def _honest_answers(honest):
    q = honest["quote"]
    if honest["prefers"] == "A":
        return ("FIRST", q), ("SECOND", q)
    if honest["prefers"] == "B":
        return ("SECOND", q), ("FIRST", q)
    return ("TIE", ""), ("TIE", "")


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_scenario_end_to_end(env, scenario):
    cid = env.ready(
        a_text=read(scenario["a_file"]),
        b_text=read(scenario["b_file"]),
        facts=MM.FACTS,
    )
    if scenario["honest"] is not None:
        env.answers(*_honest_answers(scenario["honest"]))
    env.judge(cid)

    result = env.c.get_result(cid)
    assert result["status"] == "JUDGED"
    assert result["verdict"] == scenario["expected_verdict"]
    assert result["reason"] in scenario["allowed_reasons"]
    assert result["missing_a"] == scenario["missing_a"]
    assert result["missing_b"] == scenario["missing_b"]
    expected_winner = {
        "A_WINS": env.entrant_a, "B_WINS": env.entrant_b,
    }.get(scenario["expected_verdict"])
    if expected_winner is None:
        assert result["winner"] == ""
    else:
        assert result["winner"].lower() == hex_of(expected_winner)
    # and an honest second validator, looking at the same pages and the same model, agrees
    assert env.vm.run_validator() is True


def test_the_two_clear_vs_dense_scenarios_pick_different_slots(env):
    """The same pair in swapped slots must flip the verdict: no slot favouritism in the contract."""
    verdicts = []
    for scenario in SCENARIOS[:2]:
        env.reset()
        cid = env.ready(a_text=read(scenario["a_file"]), b_text=read(scenario["b_file"]), facts=MM.FACTS)
        env.answers(*_honest_answers(scenario["honest"]))
        env.judge(cid)
        verdicts.append(env.c.verdict_of(cid))
    assert verdicts == ["A_WINS", "B_WINS"]

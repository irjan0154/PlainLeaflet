"""The validator against honest and forged leaders (Direct Mode run_validator).

Every test first runs one real judge() call so a validator is captured, then
changes what the validator sees (web pages, model answers) or what the leader
claims, and asks whether the validator would agree.
"""
import json

import pytest

from helpers import A_QUOTE, A_TEXT, B_QUOTE, B_TEXT, URL_A, URL_B
from pure_loader import L

OTHER_A_QUOTE = "Not for children under 12"       # a different, still genuine, sentence of A
NO_CHILDREN = "Take 2 tablets with water. Keep away from heat.\n"


def good_a_win():
    return L.build_result([], [], "A", "A", A_QUOTE, A_QUOTE)


def after_a_win(env):
    """Judge once (A wins) and wipe the mocks so the test can set the validator's view."""
    env.judged_a_wins()
    env.vm.clear_mocks()


# ============ honest validators ============

def test_honest_validator_agrees_with_an_honest_leader(env):
    env.judged_a_wins()
    assert env.vm.run_validator() is True


def test_honest_validator_agrees_on_b_win(env):
    cid = env.ready()
    env.honest_prefers_b()
    env.judge(cid)
    assert env.vm.run_validator() is True


def test_honest_validator_agrees_on_a_forfeit(env):
    cid = env.ready(a_text=NO_CHILDREN)
    env.judge(cid)
    assert env.vm.run_validator() is True


def test_honest_validator_agrees_on_disqualification(env):
    cid = env.ready(a_text="Take two tablets.\n", b_text="Swallow 2 pills.\n")
    env.judge(cid)
    assert env.vm.run_validator() is True


def test_validators_agree_on_the_same_recorded_problem(env):
    cid = env.ready()
    env.vm.clear_mocks()
    env.serve(URL_A, "page edited after submission\n")
    env.serve(URL_B, B_TEXT)
    env.judge(cid)
    assert env.c.get_contest(cid)["last_problem"] == "A:HASH_MISMATCH"
    assert env.vm.run_validator() is True


def test_validator_with_other_valid_quotes_still_agrees(env):
    after_a_win(env)
    env.serve_entries()
    env.answers(("FIRST", OTHER_A_QUOTE), ("SECOND", OTHER_A_QUOTE))
    assert env.vm.run_validator() is True


def test_same_verdict_reached_by_a_different_path_agrees(env):
    """TIE by agreement and TIE by order dependence are both TIE: the reason is not compared."""
    cid = env.ready()
    env.answers(("TIE", ""), ("TIE", ""))
    env.judge(cid)
    assert env.c.get_result(cid)["reason"] == "CONSISTENT_TIE"
    env.vm.clear_mocks()
    env.serve_entries()
    env.answers(("FIRST", A_QUOTE), ("FIRST", B_QUOTE))     # order dependent
    assert env.vm.run_validator() is True


# ============ a forged leader result ============

def test_leader_cannot_flip_the_verdict(env):
    env.judged_a_wins()
    forged = L.build_result([], [], "B", "B", B_QUOTE, B_QUOTE)
    assert env.vm.run_validator(leader_result=forged) is False


def test_leader_cannot_invent_a_quote(env):
    env.judged_a_wins()
    forged = L.build_result([], [], "A", "A", "a sentence nobody ever wrote", A_QUOTE)
    assert env.vm.run_validator(leader_result=forged) is False
    forged = L.build_result([], [], "A", "A", A_QUOTE, "another invented sentence")
    assert env.vm.run_validator(leader_result=forged) is False


def test_leader_cannot_quote_the_other_entry(env):
    env.judged_a_wins()
    forged = L.build_result([], [], "A", "A", B_QUOTE, B_QUOTE)
    assert env.vm.run_validator(leader_result=forged) is False


def test_leader_cannot_use_a_too_short_quote(env):
    env.judged_a_wins()
    forged = L.build_result([], [], "A", "A", "Take 2", "Take 2")
    assert env.vm.run_validator(leader_result=forged) is False


def test_leader_cannot_claim_a_missing_fact(env):
    env.judged_a_wins()
    assert env.vm.run_validator(leader_result=L.build_result([0], [], None, None, "", "")) is False
    assert env.vm.run_validator(leader_result=L.build_result([], [1], None, None, "", "")) is False
    assert env.vm.run_validator(leader_result=L.build_result([0, 1], [0, 1], None, None, "", "")) is False


def test_leader_cannot_hide_a_missing_fact(env):
    cid = env.ready(a_text=NO_CHILDREN)
    env.judge(cid)
    env.vm.clear_mocks()
    env.serve_entries()
    env.honest_prefers_a()
    # the leader pretends nothing is missing and that A won on merit
    assert env.vm.run_validator(leader_result=good_a_win()) is False
    # or reports the wrong fact index
    assert env.vm.run_validator(leader_result=L.build_result([0], [], None, None, "", "")) is False


def test_leader_cannot_attach_quotes_to_a_result_that_has_none(env):
    cid = env.ready(a_text=NO_CHILDREN)
    env.judge(cid)
    honest = L.build_result([1], [], None, None, "", "")
    assert env.vm.run_validator(leader_result=honest) is True
    assert env.vm.run_validator(leader_result=dict(honest, q1=A_QUOTE)) is False
    assert env.vm.run_validator(leader_result=dict(honest, q2="smuggled text here")) is False


def test_leader_cannot_pick_a_reason_the_verdict_does_not_allow(env):
    env.judged_a_wins()
    assert env.vm.run_validator(leader_result=dict(good_a_win(), reason="B_FAILED_FACTS")) is False
    assert env.vm.run_validator(leader_result=dict(good_a_win(), reason="CONSISTENT_TIE")) is False
    assert env.vm.run_validator(leader_result=dict(good_a_win(), reason="whatever")) is False


def test_leader_cannot_use_an_unknown_verdict(env):
    env.judged_a_wins()
    assert env.vm.run_validator(leader_result=dict(good_a_win(), verdict="A_WINS_BIG")) is False
    assert env.vm.run_validator(leader_result=dict(good_a_win(), verdict=None)) is False


@pytest.mark.parametrize("forged", [
    None,
    "A_WINS",
    42,
    [],
    {},
    {"verdict": "A_WINS"},
    {"problem": "A:NOT_A_REAL_CODE"},
    {"problem": 5},
])
def test_leader_result_of_the_wrong_shape_is_rejected(env, forged):
    env.judged_a_wins()
    assert env.vm.run_validator(leader_result=forged) is False


def test_leader_result_with_an_extra_key_is_rejected(env):
    env.judged_a_wins()
    assert env.vm.run_validator(leader_result=dict(good_a_win(), bonus="x")) is False


def test_leader_result_with_bad_index_lists_is_rejected(env):
    env.judged_a_wins()
    for bad in ([True], [-1], [1, 0], [0, 0], ["0"], 0):
        forged = dict(good_a_win(), missing_a=bad)
        assert env.vm.run_validator(leader_result=forged) is False


def test_leader_cannot_claim_a_problem_for_a_clean_round(env):
    env.judged_a_wins()
    assert env.vm.run_validator(leader_result={"problem": "A:HASH_MISMATCH"}) is False


def test_leader_cannot_hide_a_real_problem_behind_a_verdict(env):
    cid = env.ready()
    env.vm.clear_mocks()
    env.serve(URL_A, "changed after submission\n")
    env.serve(URL_B, B_TEXT)
    env.judge(cid)                                  # recorded as a problem
    assert env.vm.run_validator(leader_result=good_a_win()) is False


def test_leader_and_validator_must_name_the_same_problem(env):
    cid = env.ready()
    env.vm.clear_mocks()
    env.serve(URL_A, "changed A\n")
    env.serve(URL_B, B_TEXT)
    env.judge(cid)                                   # A:HASH_MISMATCH
    assert env.vm.run_validator(leader_result={"problem": "A:HASH_MISMATCH"}) is True
    assert env.vm.run_validator(leader_result={"problem": "B:HASH_MISMATCH"}) is False
    assert env.vm.run_validator(leader_result={"problem": "A:TOO_LARGE"}) is False


# ============ the validator sees something different ============

def test_validator_that_sees_a_changed_page_disagrees(env):
    after_a_win(env)
    env.serve(URL_A, "someone replaced this page\n")
    env.serve(URL_B, B_TEXT)
    assert env.vm.run_validator() is False


def test_validator_whose_model_prefers_the_other_entry_disagrees(env):
    after_a_win(env)
    env.serve_entries()
    env.honest_prefers_b()
    assert env.vm.run_validator() is False


def test_validator_whose_model_calls_a_tie_disagrees_with_a_win(env):
    after_a_win(env)
    env.serve_entries()
    env.answers(("TIE", ""), ("TIE", ""))
    assert env.vm.run_validator() is False


def test_validator_whose_model_is_unsure_disagrees(env):
    after_a_win(env)
    env.serve_entries()
    env.answers(("UNCLEAR", ""), ("UNCLEAR", ""))
    assert env.vm.run_validator() is False


def test_validator_whose_model_returns_garbage_disagrees(env):
    after_a_win(env)
    env.serve_entries()
    env.vm.mock_llm(r"(?s).*FIRST TEXT START.*", json.dumps({"winner": "BOTH", "quote": ""}))
    assert env.vm.run_validator() is False


def test_validator_that_cannot_fetch_a_page_disagrees(env):
    after_a_win(env)
    env.serve(URL_A, "gone", status=404)
    env.serve(URL_B, B_TEXT)
    assert env.vm.run_validator() is False


def test_validator_with_no_network_disagrees(env):
    after_a_win(env)
    assert env.vm.run_validator() is False


def test_validator_that_sees_a_missing_fact_disagrees_with_a_clean_result(env):
    after_a_win(env)
    env.serve(URL_A, NO_CHILDREN)        # hash differs too, but the point stands
    env.serve(URL_B, B_TEXT)
    assert env.vm.run_validator() is False


# ============ leader errors, by class ============

def world(env, kind):
    """Set what the validator's own fetch/model run will see."""
    env.vm.clear_mocks()
    if kind == "ok":
        env.serve_entries()
        env.honest_prefers_a()
    elif kind == "a404":
        env.serve(URL_A, "gone", status=404)
        env.serve(URL_B, B_TEXT)
    elif kind == "a403":
        env.serve(URL_A, "forbidden", status=403)
        env.serve(URL_B, B_TEXT)
    elif kind == "b503":
        env.serve(URL_A, A_TEXT)
        env.serve(URL_B, "down", status=503)
    elif kind == "b502":
        env.serve(URL_A, A_TEXT)
        env.serve(URL_B, "bad gateway", status=502)
    elif kind == "llm_bad":
        env.serve_entries()
        env.vm.mock_llm(r"(?s).*FIRST TEXT START.*", json.dumps({"nope": 1}))
    else:
        raise AssertionError(kind)


@pytest.mark.parametrize("leader_msg,validator_sees,agrees", [
    # deterministic errors must match exactly
    ("[EXTERNAL] HTTP 404 for entry A", "a404", True),
    ("[EXTERNAL] HTTP 403 for entry A", "a404", False),
    ("[EXTERNAL] HTTP 404 for entry A", "a403", False),
    ("[EXTERNAL] HTTP 404 for entry A", "ok", False),
    ("[EXTERNAL] HTTP 404 for entry A", "b503", False),
    ("[EXPECTED] NOT_JUDGEABLE", "ok", False),
    ("[EXPECTED] NOT_JUDGEABLE", "a404", False),
    # transient errors agree when both sides are transient, whatever the status
    ("[TRANSIENT] HTTP 503 for entry B", "b503", True),
    ("[TRANSIENT] HTTP 503 for entry B", "b502", True),
    ("[TRANSIENT] fetch failed for entry A", "b503", True),
    ("[TRANSIENT] HTTP 503 for entry B", "ok", False),
    ("[TRANSIENT] HTTP 503 for entry B", "a404", False),
    ("[EXTERNAL] HTTP 404 for entry A", "b503", False),
    # model errors never agree: the round must move to another leader
    ("[LLM_ERROR] bad judgement: JUDGEMENT_KEYS", "llm_bad", False),
    ("[LLM_ERROR] bad judgement: JUDGEMENT_KEYS", "ok", False),
    ("[LLM_ERROR] bad judgement: JUDGEMENT_KEYS", "a404", False),
    # unknown errors never agree
    ("boom", "ok", False),
    ("boom", "a404", False),
    ("", "ok", False),
])
def test_leader_error_handling(env, leader_msg, validator_sees, agrees):
    after_a_win(env)
    world(env, validator_sees)
    assert env.vm.run_validator(leader_error=Exception(leader_msg)) is agrees


def test_a_leader_error_never_agrees_when_the_validator_fails_the_same_way_unexpectedly(env):
    after_a_win(env)
    env.vm.clear_mocks()          # no web mocks: the validator's fetch fails as TRANSIENT
    assert env.vm.run_validator(leader_error=Exception("[EXTERNAL] HTTP 404 for entry A")) is False
    assert env.vm.run_validator(leader_error=Exception("[TRANSIENT] fetch failed for entry A")) is True


# ============ extra edges (found while preparing the mutation run) ============

def test_leader_error_and_a_validator_that_crashes_outside_the_contract_rules_disagree(env):
    """The validator's own run raises something that is not a UserError (no model mock at all)."""
    after_a_win(env)
    env.serve_entries()                       # pages are fine, the model has no mock: the round crashes
    assert env.vm.run_validator(leader_error=Exception("[TRANSIENT] fetch failed for entry A")) is False


def test_external_error_agreement_needs_the_exact_same_message(env):
    after_a_win(env)
    world(env, "a404")
    assert env.vm.run_validator(leader_error=Exception("[EXTERNAL] HTTP 404 for entry A")) is True
    assert env.vm.run_validator(leader_error=Exception("[EXTERNAL] HTTP 404 for entry B")) is False

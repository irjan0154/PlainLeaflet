#!/usr/bin/env python3
"""Mutation run: break one rule of the contract at a time and see if the tests notice.

    python scripts/mutate.py --check              # every mutation applies exactly once (no tests run)
    python scripts/mutate.py --list
    python scripts/mutate.py                      # run all (about 10 minutes)
    python scripts/mutate.py --from 1 --to 40     # run a slice; results accumulate in the report
    python scripts/mutate.py --only P05,C12

Work happens on a COPY of the project in a temp directory, so an interrupted run
cannot leave the real contract broken. Do not run two copies of this script at
the same time (the test tool writes an `artifacts` folder).

Outcome per mutant:
  KILLED    the test suite failed (good)
  SURVIVED  the suite still passed: either add a test, or argue why the change
            cannot alter behaviour (the `equivalent` field below)
  INVALID   the mutant does not even import: a bad mutation, fix it here
"""
import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT = pathlib.Path("contracts/plain_leaflet.py")
DEFAULT_REPORT = ROOT / "docs" / "mutation_report.json"


def M(mid, desc, old, new, equivalent=None):
    return {"id": mid, "desc": desc, "old": old, "new": new, "equivalent": equivalent}


MUTANTS = [
    # ---------------- pure logic: hashing, text, addresses ----------------
    M("P01", "hash is not SHA-256", "return hashlib.sha256(data).hexdigest()", "return hashlib.sha1(data).hexdigest()"),
    M("P02", "uppercase hex digests accepted", 're.fullmatch(r"[0-9a-f]{64}", value)', 're.fullmatch(r"[0-9a-fA-F]{64}", value)'),
    M("P03", "text matching becomes case-sensitive", 'return re.sub(r"\\s+", " ", text.casefold()).strip()', 'return re.sub(r"\\s+", " ", text).strip()'),
    M("P04", "only plain spaces are collapsed", 're.sub(r"\\s+", " ", text.casefold())', 're.sub(r"[ ]+", " ", text.casefold())'),
    M("P05", "normalised text is not stripped", '" ", text.casefold()).strip()', '" ", text.casefold())'),
    # ---------------- pure logic: URL admission ----------------
    M("P06", "http accepted", 'r"^https://(?P<host>"', 'r"^https?://(?P<host>"'),
    M("P07", "any port accepted", 'r"(?::443)?(?P<path>', 'r"(?::[0-9]+)?(?P<path>'),
    M("P08", ".localhost not blocked", '".localhost", ', ""),
    M("P09", ".local not blocked", '".local", ', ""),
    M("P10", ".internal not blocked", '".internal", ', ""),
    M("P11", ".lan not blocked", '".lan", ', ""),
    M("P12", ".home.arpa not blocked", '".home.arpa", ', ""),
    M("P13", ".invalid not blocked", ', ".invalid")', ")"),
    M("P14", "numeric last label (IPv4) accepted", 're.fullmatch(r"[a-z][a-z0-9-]*", tld)', 're.fullmatch(r"[a-z0-9-]*", tld)'),
    M("P15", "URL length limit off by one", "len(url) > MAX_URL_LEN", "len(url) >= MAX_URL_LEN"),
    M("P16", "non-ASCII URLs accepted", "if url != url.strip() or not url.isascii():", "if url != url.strip():"),
    M("P17", "surrounding whitespace accepted", "if url != url.strip() or not url.isascii():", "if not url.isascii():"),
    M("P18", "non-string URL not rejected up front", "if not isinstance(url, str) or len(url) > MAX_URL_LEN:", "if len(url) > MAX_URL_LEN:"),
    # ---------------- pure logic: decoding ----------------
    M("P19", "size limit off by one", "if len(body) > MAX_ENTRY_BYTES:\n        raise ValueError", "if len(body) >= MAX_ENTRY_BYTES:\n        raise ValueError"),
    M("P20", "BOM accepted", 'if text.startswith("\\ufeff"):', "if False:"),
    M("P21", "NUL accepted", 'if "\\x00" in text:', "if False:"),
    M("P22", "blank text accepted", 'if text.strip() == "":', 'if text == "":'),
    M("P23", "invalid UTF-8 accepted", 'text = body.decode("utf-8")', 'text = body.decode("utf-8", errors="replace")'),
    # ---------------- pure logic: facts parsing ----------------
    M("P24", "empty fact list accepted", "if not (MIN_FACTS <= len(data) <= MAX_FACTS):", "if not (0 <= len(data) <= MAX_FACTS):"),
    M("P25", "fact list limit off by one", "if not (MIN_FACTS <= len(data) <= MAX_FACTS):", "if not (MIN_FACTS <= len(data) < MAX_FACTS):"),
    M("P26", "fact minimum length off by one", "if not (MIN_FACT_LEN <= len(fact) <= MAX_FACT_LEN):", "if not (MIN_FACT_LEN < len(fact) <= MAX_FACT_LEN):"),
    M("P27", "fact maximum length off by one", "if not (MIN_FACT_LEN <= len(fact) <= MAX_FACT_LEN):", "if not (MIN_FACT_LEN <= len(fact) < MAX_FACT_LEN):"),
    M("P28", "duplicate facts accepted", "if key in seen:", "if False:"),
    M("P29", "duplicate check is case-sensitive", "key = normalize_text(fact)", "key = fact"),
    M("P30", "facts are not stripped", "fact = item.strip()", "fact = item"),
    M("P31", "non-string fact not rejected", "if not isinstance(item, str):\n            raise ValueError", "if False:\n            raise ValueError"),
    # ---------------- pure logic: whole-phrase fact matching ----------------
    M("P32", "empty fact counts as found", 'if needle == "":\n        return False', 'if False:\n        return False'),
    M("P33", "no letter/digit boundary before the fact", "if before.isalnum():", "if False:"),
    M("P34", "no decimal check before the fact", "before in \".,\"\n                and needle[0].isdigit()\n                and pos >= 2\n                and hay[pos - 2].isdigit()", "False"),
    M("P35", "decimal comma not treated like a point (before)", 'before in ".,"', 'before in "."'),
    M("P36", "decimal check before ignores that the fact starts with a digit", "                and needle[0].isdigit()\n", ""),
    M("P37", "start-of-text guard weakened", "and pos >= 2\n", "and pos >= 1\n"),
    M("P38", "no letter/digit boundary after the fact", "if after.isalnum():", "if False:"),
    M("P39", "no decimal check after the fact", 'after in ".,"\n                and needle[-1].isdigit()\n                and end + 1 < len(hay)\n                and hay[end + 1].isdigit()', "False"),
    M("P40", "decimal comma not treated like a point (after)", 'after in ".,"', 'after in "."'),
    M("P41", "decimal check after ignores that the fact ends with a digit", "                and needle[-1].isdigit()\n", ""),
    M("P42", "end-of-text guard weakened", "and end + 1 < len(hay)", "and end + 1 <= len(hay)"),
    M("P43", "next search skips overlapping occurrences", "start = pos + 1", "start = end"),
    M("P44", "boundary rule applies only when the fact starts with a digit", "if needle[0].isalnum() and pos > 0:", "if needle[0].isdigit() and pos > 0:"),
    M("P45", "missing_facts reports found facts", "if not fact_in_text(fact, text)]", "if fact_in_text(fact, text)]"),
    # ---------------- pure logic: quotes and the model answer ----------------
    M("P46", "quote minimum length off by one", "if len(nq) < MIN_QUOTE_LEN:", "if len(nq) <= MIN_QUOTE_LEN:"),
    M("P47", "any quote accepted", "return nq in normalize_text(text)", "return True"),
    M("P48", "non-string quote accepted", "if not isinstance(quote, str):\n        return False\n    nq", "if False:\n        return False\n    nq"),
    M("P49", "extra keys in the model answer accepted", 'if set(raw.keys()) != {"winner", "quote"}:', 'if not {"winner", "quote"} <= set(raw.keys()):'),
    M("P50", "unknown winner label accepted", "if not isinstance(winner, str) or winner not in JUDGE_WINNERS:", "if not isinstance(winner, str):"),
    M("P51", "non-string quote in the answer accepted", "if not isinstance(quote, str):\n        raise ValueError", "if False:\n        raise ValueError"),
    M("P52", "quote in the answer is not truncated", 'return {"winner": winner, "quote": quote[:MAX_QUOTE_LEN]}', 'return {"winner": winner, "quote": quote}'),
    M("P53", "FIRST maps to the wrong entry", "return L_B if swapped else L_A", "return L_A if swapped else L_B"),
    M("P54", "SECOND maps to the wrong entry", "return L_A if swapped else L_B", "return L_B if swapped else L_A"),
    M("P55", "TIE answer becomes UNCLEAR", "if winner == W_TIE:\n        return L_TIE", "if winner == W_TIE:\n        return L_UNCLEAR"),
    M("P56", "quote of A is checked in B", "return L_A if quote_in_text(quote, a_text) else L_UNCLEAR", "return L_A if quote_in_text(quote, b_text) else L_UNCLEAR"),
    M("P57", "quote of B is checked in A", "return L_B if quote_in_text(quote, b_text) else L_UNCLEAR", "return L_B if quote_in_text(quote, a_text) else L_UNCLEAR"),
    M("P58", "A's quote not checked at all", "return L_A if quote_in_text(quote, a_text) else L_UNCLEAR", "return L_A"),
    M("P59", "B's quote not checked at all", "return L_B if quote_in_text(quote, b_text) else L_UNCLEAR", "return L_B"),
    # ---------------- pure logic: the verdict rule ----------------
    M("P60", "one failing entry disqualifies both", "if a_failed and b_failed:\n        return V_DISQUALIFIED", "if a_failed or b_failed:\n        return V_DISQUALIFIED"),
    M("P61", "A failing facts hands the win to A", "return V_B_WINS, R_A_FAILED", "return V_A_WINS, R_A_FAILED"),
    M("P62", "B failing facts hands the win to B", "return V_A_WINS, R_B_FAILED", "return V_B_WINS, R_B_FAILED"),
    M("P63", "unknown order results tolerated", "if r1 not in RESOLVED_LABELS or r2 not in RESOLVED_LABELS:", "if r1 not in RESOLVED_LABELS and r2 not in RESOLVED_LABELS:"),
    M("P64", "doubt in only one order does not stop a winner", "if r1 == L_UNCLEAR or r2 == L_UNCLEAR:", "if r1 == L_UNCLEAR and r2 == L_UNCLEAR:"),
    M("P65", "agreement check removed", "    if r1 == r2:\n        if r1 == L_A:", "    if True:\n        if r1 == L_A:"),
    M("P66", "A consistent win goes to B", "if r1 == L_A:\n            return V_A_WINS, R_CONSISTENT", "if r1 == L_A:\n            return V_B_WINS, R_CONSISTENT"),
    M("P67", "B consistent win goes to A", "if r1 == L_B:\n            return V_B_WINS, R_CONSISTENT", "if r1 == L_B:\n            return V_A_WINS, R_CONSISTENT"),
    M("P68", "agreeing TIE becomes a win", "return V_TIE, R_CONSISTENT_TIE", "return V_A_WINS, R_CONSISTENT"),
    M("P69", "order-dependent answer is not a tie", "return V_TIE, R_ORDER_DEPENDENT", "return V_UNDETERMINED, R_JUDGE_UNCLEAR"),
    # ---------------- pure logic: the stored result and validator agreement ----------------
    M("P70", "quotes kept for results that should have none", " and reason == R_CONSISTENT\n", "\n"),
    M("P71", "q1 always kept", 'q1[:MAX_QUOTE_LEN] if keep_quotes else ""', "q1[:MAX_QUOTE_LEN]"),
    M("P72", "q2 always kept", 'q2[:MAX_QUOTE_LEN] if keep_quotes else ""', "q2[:MAX_QUOTE_LEN]"),
    M("P73", "unsorted or duplicate indexes accepted", "        and value == sorted(set(value))\n", ""),
    M("P74", "booleans accepted as indexes", "isinstance(v, int) and not isinstance(v, bool) and v >= 0", "isinstance(v, int) and v >= 0"),
    M("P75", "negative index accepted", "and v >= 0 for v in value", "and v >= -1 for v in value"),
    M("P76", "extra or missing result keys accepted", 'if set(result.keys()) != {"missing_a", "missing_b", "verdict", "reason", "q1", "q2"}:', "if False:"),
    M("P77", "non-string quotes in a result accepted", 'if not isinstance(result["q1"], str) or not isinstance(result["q2"], str):', "if False:"),
    M("P78", "reason not tied to its verdict", 'if verdict not in VERDICTS or result["reason"] not in ALLOWED_REASONS[verdict]:', "if verdict not in VERDICTS:"),
    M("P79", "forfeit verdicts not enforced", 'if expected is not None and (verdict, result["reason"]) != expected:', "if False:"),
    M("P80", "forfeit reasons allowed without a forfeit", 'if expected is None and result["reason"] in (R_A_FAILED, R_B_FAILED, R_BOTH_FAILED):', "if False:"),
    M("P81", "missing list of A not compared", 'if leader["missing_a"] != mine["missing_a"] or leader["missing_b"] != mine["missing_b"]:', 'if leader["missing_b"] != mine["missing_b"]:'),
    M("P82", "missing list of B not compared", 'if leader["missing_a"] != mine["missing_a"] or leader["missing_b"] != mine["missing_b"]:', 'if leader["missing_a"] != mine["missing_a"]:'),
    M("P83", "verdict not compared", 'if leader["verdict"] != mine["verdict"]:', "if False:"),
    M("P84", "first quote not verified", 'return quote_in_text(leader["q1"], text) and quote_in_text(leader["q2"], text)', 'return quote_in_text(leader["q2"], text)'),
    M("P85", "second quote not verified", 'return quote_in_text(leader["q1"], text) and quote_in_text(leader["q2"], text)', 'return quote_in_text(leader["q1"], text)'),
    M("P86", "one genuine quote is enough", 'return quote_in_text(leader["q1"], text) and quote_in_text(leader["q2"], text)', 'return quote_in_text(leader["q1"], text) or quote_in_text(leader["q2"], text)'),
    M("P87", "quotes checked in the wrong entry", "text = a_text if verdict == V_A_WINS else b_text", "text = b_text if verdict == V_A_WINS else a_text"),
    M("P88", "stray quotes allowed in non-decisive results", 'return leader["q1"] == "" and leader["q2"] == ""', "return True"),
    M("P89", "problem entry label not validated", 'if entry not in ("A", "B") or code not in PROBLEM_CODES:', "if code not in PROBLEM_CODES:"),
    M("P90", "problem code not validated", 'if entry not in ("A", "B") or code not in PROBLEM_CODES:', 'if entry not in ("A", "B"):'),
    M("P91", "malformed problem value accepted", 'if not isinstance(value, str) or ":" not in value:', "if False:"),
    M("P92", "problem entry not validated on read", 'return entry in ("A", "B") and code in PROBLEM_CODES', "return code in PROBLEM_CODES"),
    M("P93", "different problems agree", 'return is_problem(leader) and is_problem(mine) and leader["problem"] == mine["problem"]', "return is_problem(leader) and is_problem(mine)"),
    M("P94", "leader's problem shape not checked", 'return is_problem(leader) and is_problem(mine) and leader["problem"] == mine["problem"]', 'return is_problem(mine) and leader["problem"] == mine["problem"]'),
    M("P95", "problem vs result mismatch tolerated", "if leader_problem or mine_problem:", "if leader_problem and mine_problem:",
      equivalent="if exactly one side is a problem, the fall-through to rounds_agree rejects it anyway, because a problem dict is not a well-formed result; the `or` only states the intent"),
    M("P96", "delimiters are not defanged", 'return re.sub(r"={3,}", "==", text)', "return text"),
    M("P97", "defang misses five-character delimiters", 'r"={3,}"', 'r"={6,}"'),
    M("P98", "defang puts the delimiter back", '"==", text)', '"=====", text)'),
    M("P99", "prompt no longer marks the texts untrusted", "UNTRUSTED DATA", "DATA"),
    M("P100", "first text placed in the second slot", "+ defang(first_text)", "+ defang(second_text)"),
    # ---------------- contract: fetching ----------------
    M("C01", "HTTP 500 treated as external", "if status >= 500:", "if status > 500:"),
    M("C02", "redirects accepted as a final answer", "if status != 200:", "if status >= 400:"),
    M("C03", "5xx classed as external", 'f"{ERROR_TRANSIENT} HTTP {status} for entry {label}"', 'f"{ERROR_EXTERNAL} HTTP {status} for entry {label}"'),
    M("C04", "4xx classed as transient", 'f"{ERROR_EXTERNAL} HTTP {status} for entry {label}"', 'f"{ERROR_TRANSIENT} HTTP {status} for entry {label}"'),
    M("C05", "network failure classed as external", 'f"{ERROR_TRANSIENT} fetch failed for entry {label}"', 'f"{ERROR_EXTERNAL} fetch failed for entry {label}"'),
    M("C06", "empty body not handled", 'bodies.append(body if body is not None else b"")', "bodies.append(body)"),
    M("C07", "size check before hashing removed", "        if len(body) > MAX_ENTRY_BYTES:\n            return make_problem(label, \"TOO_LARGE\"), \"\", \"\"\n", ""),
    M("C08", "hash not verified", "if sha256_hex(body) != expected_sha:", "if False:"),
    M("C09", "hash problem blames entry A", 'return make_problem(label, "HASH_MISMATCH"), "", ""', 'return make_problem("A", "HASH_MISMATCH"), "", ""'),
    M("C10", "decode problem has a fixed code", 'return make_problem(label, str(exc)), "", ""', 'return make_problem(label, "NOT_UTF8"), "", ""'),
    M("C11", "model asked even when a fact is missing in only one entry", "if missing_a or missing_b:", "if missing_a and missing_b:"),
    M("C12", "model asked only in one order", "for swapped in (False, True):", "for swapped in (False,):"),
    M("C13", "second order is not swapped", "for swapped in (False, True):", "for swapped in (False, False):"),
    M("C14", "texts are never swapped in the prompt", "first, second = (b_text, a_text) if swapped else (a_text, b_text)", "first, second = (a_text, b_text)"),
    M("C15", "answer not mapped back for the swapped order", 'label = resolve_order(judgement["winner"], swapped)', 'label = resolve_order(judgement["winner"], False)'),
    M("C16", "quote not verified in the round", 'resolved.append(verify_quote(label, judgement["quote"], a_text, b_text))', "resolved.append(label)"),
    M("C17", "model trouble classed as a business error", 'f"{ERROR_LLM} bad judgement: {exc}"', 'f"{ERROR_EXPECTED} bad judgement: {exc}"'),
    M("C18", "the same quote reused for both orders", "quotes.append(judgement[\"quote\"])", "quotes.append(quotes[0] if quotes else judgement[\"quote\"])"),
    # ---------------- contract: leader error handling ----------------
    M("C19", "deterministic errors agree without comparing", "return validator_msg == leader_msg", "return True"),
    M("C20", "transient needs only one side", "if validator_msg.startswith(ERROR_TRANSIENT) and leader_msg.startswith(ERROR_TRANSIENT):", "if validator_msg.startswith(ERROR_TRANSIENT) or leader_msg.startswith(ERROR_TRANSIENT):"),
    M("C21", "model errors agree", "return False  # model trouble or unknown: force a new leader", "return True  # model trouble or unknown: force a new leader"),
    M("C22", "leader failed but validator succeeded still agrees", "return False  # the leader failed, this validator did not", "return True  # the leader failed, this validator did not"),
    M("C23", "unexpected validator crash agrees", "    except Exception:\n        return False\n", "    except Exception:\n        return True\n"),
    M("C24", "external errors not compared exactly", "if validator_msg.startswith(ERROR_EXPECTED) or validator_msg.startswith(ERROR_EXTERNAL):", "if validator_msg.startswith(ERROR_EXPECTED):"),
    # ---------------- contract: open_contest ----------------
    M("C25", "label maximum off by one", "if not (1 <= len(label) <= MAX_LABEL_LEN):", "if not (1 <= len(label) < MAX_LABEL_LEN):"),
    M("C26", "empty label accepted", "if not (1 <= len(label) <= MAX_LABEL_LEN):", "if not (0 <= len(label) <= MAX_LABEL_LEN):"),
    M("C27", "label not stripped", "label = label.strip()", "label = label"),
    M("C28", "fact errors lose their code", "raise _expected(str(exc))", 'raise _expected("FACTS")'),
    M("C29", "open limit off by one", "if self._open_count(organizer) >= MAX_OPEN_PER_ORGANIZER:", "if self._open_count(organizer) > MAX_OPEN_PER_ORGANIZER:"),
    M("C30", "contest ids skip", "self.next_id = u256(int(contest_id) + 1)", "self.next_id = u256(int(contest_id) + 2)"),
    M("C31", "opening does not take a slot", "self.open_by_organizer[organizer] = u256(self._open_count(organizer) + 1)", "self.open_by_organizer[organizer] = u256(self._open_count(organizer))"),
    M("C32", "facts stored as typed, not normalised", "facts_json=json.dumps(facts),", "facts_json=facts_json,"),
    M("C33", "new contest not open", "status=STATUS_OPEN,", "status=STATUS_JUDGED,"),
    M("C34", "prize not stored", "prize_atto=prize_atto,", "prize_atto=u256(0),"),
    M("C35", "first contest id is 0", "self.next_id = u256(1)\n", "self.next_id = u256(0)\n"),
    M("C36", "releasing a slot does nothing", "u256(count - 1 if count > 0 else 0)", "u256(count)",),
    M("C37", "release can go below zero", "count - 1 if count > 0 else 0", "count - 1",
      equivalent="every release pairs with an earlier increment in open_contest, so count is always at least 1 when release runs; the guard is a defensive floor"),
    # ---------------- contract: submit_entry ----------------
    M("C38", "entries accepted into closed contests", "if contest.status != STATUS_OPEN:\n            raise _expected(\"NOT_OPEN\")\n        if contest.a_filled", "if False:\n            raise _expected(\"NOT_OPEN\")\n        if contest.a_filled"),
    M("C39", "third entry accepted", "if contest.a_filled and contest.b_filled:\n            raise _expected(\"CONTEST_FULL\")", "if False:\n            raise _expected(\"CONTEST_FULL\")"),
    M("C40", "full only when B is filled", "if contest.a_filled and contest.b_filled:\n            raise _expected(\"CONTEST_FULL\")", "if contest.b_filled:\n            raise _expected(\"CONTEST_FULL\")",
      equivalent="slot B is only ever filled after slot A, so b_filled already implies a_filled"),
    M("C41", "bad URLs accepted", "if not is_valid_https_url(url):", "if False:"),
    M("C42", "digest not lower-cased", "digest = sha256.strip().lower()", "digest = sha256.strip()"),
    M("C43", "digest not stripped", "digest = sha256.strip().lower()", "digest = sha256.lower()"),
    M("C44", "bad digests accepted", "if not is_sha256_hex(digest):", "if False:"),
    M("C45", "duplicate content accepted", "if digest == contest.a_sha256 or url == contest.a_url:", "if url == contest.a_url:"),
    M("C46", "duplicate address accepted", "if digest == contest.a_sha256 or url == contest.a_url:", "if digest == contest.a_sha256:"),
    M("C47", "second entry overwrites slot A", "contest.b_author = sender\n", "contest.a_author = sender\n"),
    M("C48", "second entry URL stored in slot A", "contest.b_url = url\n", "contest.a_url = url\n"),
    M("C49", "second entry digest stored in slot A", "contest.b_sha256 = digest\n", "contest.a_sha256 = digest\n"),
    M("C50", "second slot never marked filled", "contest.b_filled = True\n", "pass\n"),
    # ---------------- contract: withdraw ----------------
    M("C51", "anyone can withdraw", "if gl.message.sender_address != contest.organizer:", "if False:"),
    M("C52", "withdraw works on closed contests", "        if contest.status != STATUS_OPEN:\n            raise _expected(\"NOT_OPEN\")\n        contest.status = STATUS_WITHDRAWN", "        contest.status = STATUS_WITHDRAWN"),
    M("C53", "withdraw sets the wrong status", "contest.status = STATUS_WITHDRAWN\n", "contest.status = STATUS_EXHAUSTED\n"),
    M("C54", "withdraw keeps the slot", "contest.status = STATUS_WITHDRAWN\n        self._release(contest.organizer)", "contest.status = STATUS_WITHDRAWN"),
    # ---------------- contract: judge ----------------
    M("C55", "judging a closed contest allowed", "if contest.status != STATUS_OPEN:\n            raise _expected(\"NOT_JUDGEABLE\")", "if False:\n            raise _expected(\"NOT_JUDGEABLE\")"),
    M("C56", "judging without entries allowed", "if not (contest.a_filled and contest.b_filled):", "if False:"),
    M("C57", "one entry is enough to judge", "if not (contest.a_filled and contest.b_filled):", "if not (contest.a_filled or contest.b_filled):"),
    M("C58", "anyone can trigger a judgement", "if sender != contest.organizer and sender != contest.a_author and sender != contest.b_author:", "if False:"),
    M("C59", "entrant B cannot trigger a judgement", "if sender != contest.organizer and sender != contest.a_author and sender != contest.b_author:", "if sender != contest.organizer and sender != contest.a_author:"),
    M("C60", "organizer cannot trigger a judgement", "if sender != contest.organizer and sender != contest.a_author and sender != contest.b_author:", "if sender != contest.a_author and sender != contest.b_author:"),
    M("C61", "validator trusts a leader that errored", "            if not isinstance(leaders_res, gl.vm.Return):\n                return _handle_leader_error(leaders_res, leader_fn)\n", ""),
    M("C62", "leader errors always disagree", "return _handle_leader_error(leaders_res, leader_fn)", "return False"),
    M("C63", "validator failure agrees", "            except gl.vm.UserError:\n                return False\n            return outcomes_agree", "            except gl.vm.UserError:\n                return True\n            return outcomes_agree"),
    M("C64", "validator accepts any leader result", "return outcomes_agree(leaders_res.calldata, mine, a_text, b_text)", "return True"),
    M("C65", "problem attempts are not counted", "            contest.attempts = u256(int(contest.attempts) + 1)\n            contest.last_problem = outcome[\"problem\"]", "            contest.attempts = u256(int(contest.attempts))\n            contest.last_problem = outcome[\"problem\"]"),
    M("C66", "problem is not recorded", "contest.last_problem = outcome[\"problem\"]", "pass"),
    M("C67", "problems never exhaust the contest", "if int(contest.attempts) >= MAX_ATTEMPTS:\n                contest.status = STATUS_EXHAUSTED", "if int(contest.attempts) > MAX_ATTEMPTS:\n                contest.status = STATUS_EXHAUSTED"),
    M("C68", "exhausted contest keeps its slot", "contest.status = STATUS_EXHAUSTED\n                self._release(contest.organizer)", "contest.status = STATUS_EXHAUSTED"),
    M("C69", "a problem falls through to the result code", "                self._release(contest.organizer)\n            return\n\n        if not result_is_well_formed(outcome):", "                self._release(contest.organizer)\n            pass\n\n        if not result_is_well_formed(outcome):"),
    M("C70", "malformed result is stored", "        if not result_is_well_formed(outcome):\n            raise _expected(\"BAD_ROUND_RESULT\")", "        pass",
      equivalent="consensus already requires every validator to accept only well-formed results (rounds_agree calls result_is_well_formed on both sides), so a malformed outcome cannot reach this line; it is a second guard"),
    M("C71", "UNDETERMINED recorded on the first attempt", "if outcome[\"verdict\"] == V_UNDETERMINED:", "if False:"),
    M("C72", "UNDETERMINED attempts not counted", "            contest.attempts = u256(int(contest.attempts) + 1)\n            contest.last_problem = outcome[\"reason\"]", "            contest.attempts = u256(int(contest.attempts))\n            contest.last_problem = outcome[\"reason\"]"),
    M("C73", "UNDETERMINED retried one time too many", "if int(contest.attempts) < MAX_ATTEMPTS:\n                return", "if int(contest.attempts) <= MAX_ATTEMPTS:\n                return"),
    M("C74", "UNDETERMINED never retried", "if int(contest.attempts) < MAX_ATTEMPTS:\n                return", "if False:\n                return"),
    M("C75", "last_problem not cleared after a good result", "        else:\n            contest.last_problem = \"\"\n", "        else:\n            pass\n"),
    M("C76", "status not set to JUDGED", "contest.status = STATUS_JUDGED\n        contest.verdict", "contest.verdict"),
    M("C77", "verdict not stored", "contest.verdict = outcome[\"verdict\"]", "pass"),
    M("C78", "reason not stored", "contest.reason = outcome[\"reason\"]", "pass"),
    M("C79", "missing list of A not stored", "contest.missing_a_json = json.dumps(outcome[\"missing_a\"])", "pass"),
    M("C80", "missing list of B not stored", "contest.missing_b_json = json.dumps(outcome[\"missing_b\"])", "pass"),
    M("C81", "first quote not stored", "contest.q1 = outcome[\"q1\"]", "pass"),
    M("C82", "second quote not stored", "contest.q2 = outcome[\"q2\"]", "pass"),
    M("C83", "judged counter not increased", "self.judged_total = u256(int(self.judged_total) + 1)", "self.judged_total = u256(int(self.judged_total))"),
    M("C84", "judged contest keeps its slot", "self.judged_total = u256(int(self.judged_total) + 1)\n        self._release(contest.organizer)", "self.judged_total = u256(int(self.judged_total) + 1)"),
    M("C85", "round reads the wrong entry address", "url_a, sha_a = contest.a_url, contest.a_sha256", "url_a, sha_a = contest.b_url, contest.a_sha256"),
    M("C86", "round reads the wrong entry digest", "url_b, sha_b = contest.b_url, contest.b_sha256", "url_b, sha_b = contest.b_url, contest.a_sha256"),
    # ---------------- contract: reads ----------------
    M("C87", "unknown contest not rejected", "if contest_id not in self.contests:", "if False:"),
    M("C88", "winner of A is B", "if c.verdict == V_A_WINS:\n            return c.a_author.as_hex", "if c.verdict == V_A_WINS:\n            return c.b_author.as_hex"),
    M("C89", "winner of B is A", "if c.verdict == V_B_WINS:\n            return c.b_author.as_hex", "if c.verdict == V_B_WINS:\n            return c.a_author.as_hex"),
    M("C90", "winner shown for unjudged contests", "        if c.status != STATUS_JUDGED:\n            return \"\"\n        if c.verdict == V_A_WINS:", "        if c.verdict == V_A_WINS:",
      equivalent="the verdict field is written only together with status JUDGED, so for any other status the verdict is empty and the function returns an empty string anyway"),
    M("C91", "verdict shown for unjudged contests", "return c.verdict if c.status == STATUS_JUDGED else \"\"", "return c.verdict",
      equivalent="the verdict field is written only together with status JUDGED, so for any other status it is already empty"),
    M("C92", "open slots counted upwards", "return MAX_OPEN_PER_ORGANIZER - self._open_count(organizer)", "return MAX_OPEN_PER_ORGANIZER + self._open_count(organizer)"),
    M("C93", "contest counter off by one", "\"contests\": int(self.next_id) - 1,", "\"contests\": int(self.next_id),"),
    M("C94", "judged counter not reported", "\"judged\": int(self.judged_total),", "\"judged\": 0,"),
    M("C95", "empty slot A shows the zero address", "\"a_author\": c.a_author.as_hex if c.a_filled else \"\",", "\"a_author\": c.a_author.as_hex,"),
    M("C96", "empty slot B shows the zero address", "\"b_author\": c.b_author.as_hex if c.b_filled else \"\",", "\"b_author\": c.b_author.as_hex,"),
    M("C97", "attempts not reported", "\"attempts\": int(c.attempts),", "\"attempts\": 0,"),
    M("C98", "result hides the winner", "\"winner\": self._winner_hex(c),", "\"winner\": \"\","),
]


def load_report(path: pathlib.Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def apply(source: str, mutant: dict) -> str:
    count = source.count(mutant["old"])
    if count != 1:
        raise ValueError(f"{mutant['id']}: pattern occurs {count} times (need exactly 1)")
    return source.replace(mutant["old"], mutant["new"])


def make_workdir() -> pathlib.Path:
    work = pathlib.Path(tempfile.mkdtemp(prefix="plainleaflet-mutate-"))
    for name in ("contracts", "fixtures", "scripts", "tests", "pytest.ini"):
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, work / name, ignore=shutil.ignore_patterns("__pycache__", "artifacts"))
        elif src.exists():
            shutil.copy2(src, work / name)
    return work


def run_suite(work: pathlib.Path, timeout: int):
    cmd = [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "--no-header"]
    try:
        proc = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "KILLED", "timeout (the mutant hangs the suite)"
    out = proc.stdout + proc.stderr
    if proc.returncode == 0:
        return "SURVIVED", ""
    if proc.returncode == 1:
        failed = re.findall(r"^FAILED (\S+)", out, flags=re.M)
        return "KILLED", failed[0] if failed else "tests failed"
    return "INVALID", out.strip().splitlines()[-1][:200] if out.strip() else f"exit code {proc.returncode}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="only verify every mutation applies exactly once")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--only", help="comma separated ids")
    ap.add_argument("--from", dest="start", type=int, default=1, help="first mutant number (1-based)")
    ap.add_argument("--to", dest="stop", type=int, default=10**6, help="last mutant number (1-based)")
    ap.add_argument("--timeout", type=int, default=240, help="seconds per mutant")
    ap.add_argument("--report", default=str(DEFAULT_REPORT))
    ap.add_argument("--summary", action="store_true", help="print totals from the report and exit")
    ap.add_argument("--quiet", action="store_true", help="print only mutants that were not killed, plus the totals")
    args = ap.parse_args(argv)

    ids = [m["id"] for m in MUTANTS]
    if len(ids) != len(set(ids)):
        print("duplicate mutant ids", file=sys.stderr)
        return 2
    source = (ROOT / CONTRACT).read_text(encoding="utf-8")

    if args.list:
        for n, m in enumerate(MUTANTS, 1):
            print(f"{n:3d} {m['id']}  {m['desc']}" + ("   [argued equivalent]" if m["equivalent"] else ""))
        return 0

    if args.check:
        bad = 0
        for m in MUTANTS:
            try:
                mutated = apply(source, m)
                if mutated == source:
                    raise ValueError(f"{m['id']}: mutation changes nothing")
                compile(mutated, m["id"], "exec")
            except (ValueError, SyntaxError) as exc:
                bad += 1
                print("BAD", exc)
        print(f"{len(MUTANTS)} mutants, {bad} problems")
        return 1 if bad else 0

    report_path = pathlib.Path(args.report)
    report = load_report(report_path)

    if args.summary:
        return summarize(report)

    selected = [m for n, m in enumerate(MUTANTS, 1) if args.start <= n <= args.stop]
    if args.only:
        wanted = set(args.only.split(","))
        selected = [m for m in MUTANTS if m["id"] in wanted]

    work = make_workdir()
    target = work / CONTRACT
    started = time.time()
    try:
        # the unmodified copy must be green, or the whole run means nothing
        status, detail = run_suite(work, args.timeout * 3)
        if status != "SURVIVED":
            print("baseline run is not green:", status, detail, file=sys.stderr)
            return 2
        for m in selected:
            target.write_text(apply(source, m), encoding="utf-8", newline="\n")
            status, detail = run_suite(work, args.timeout)
            report[m["id"]] = {"desc": m["desc"], "outcome": status, "detail": detail,
                               "equivalent": m["equivalent"]}
            flag = "" if status == "KILLED" else ("  <-- argued equivalent" if m["equivalent"] else "  <-- LOOK")
            if status != "KILLED" or not args.quiet:
                print(f"{m['id']:4s} {status:9s} {m['desc']}{flag}", flush=True)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print(f"done in {time.time() - started:.0f}s")
    return summarize(report)


def summarize(report: dict) -> int:
    known = {m["id"]: m for m in MUTANTS}
    rows = {k: v for k, v in report.items() if k in known}
    killed = [k for k, v in rows.items() if v["outcome"] == "KILLED"]
    survived = [k for k, v in rows.items() if v["outcome"] == "SURVIVED"]
    equivalent = [k for k in survived if known[k]["equivalent"]]
    unexplained = [k for k in survived if not known[k]["equivalent"]]
    invalid = [k for k, v in rows.items() if v["outcome"] == "INVALID"]
    missing = [k for k in known if k not in rows]
    print(f"mutants {len(known)}: killed {len(killed)}, survived-and-argued-equivalent {len(equivalent)}, "
          f"survived-unexplained {len(unexplained)}, invalid {len(invalid)}, not run yet {len(missing)}")
    for k in unexplained:
        print("  UNEXPLAINED SURVIVOR", k, known[k]["desc"])
    for k in invalid:
        print("  INVALID", k, rows[k]["detail"])
    return 1 if (unexplained or invalid or missing) else 0


if __name__ == "__main__":
    raise SystemExit(main())

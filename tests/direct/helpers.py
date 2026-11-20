"""Shared fixtures-as-code for the Direct Mode tests."""
import json
import re

from pure_loader import L

CONTRACT = "contracts/plain_leaflet.py"

FACTS = ["take 2 tablets", "not for children"]
A_TEXT = "Take 2 tablets with water. Not for children under 12.\n"
B_TEXT = "Take 2 tablets with a drink. This medicine is not for children.\n"
A_QUOTE = "Take 2 tablets with water"
B_QUOTE = "Take 2 tablets with a drink"
URL_A = "https://raw.example.com/entry-a.txt"
URL_B = "https://raw.example.com/entry-b.txt"


def hex_of(account) -> str:
    """Direct Mode accounts are raw bytes; the contract returns checksummed hex."""
    return "0x" + bytes(account).hex()


def sha_of(text) -> str:
    data = text if isinstance(text, bytes) else text.encode("utf-8")
    return L.sha256_hex(data)


class Env:
    """A deployed contract plus the people and mocks around it."""

    def __init__(self, vm, contract, organizer, entrant_a, entrant_b, stranger):
        self.vm = vm
        self.c = contract
        self.organizer = organizer
        self.entrant_a = entrant_a
        self.entrant_b = entrant_b
        self.stranger = stranger
        self.a_text = A_TEXT
        self.b_text = B_TEXT

    # ----- web -----
    def serve(self, url, body, status=200):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.vm.mock_web(
            re.escape(url),
            {"response": {"status": status, "headers": {}, "body": data}, "method": "GET"},
        )

    def serve_entries(self, a_body=None, b_body=None):
        self.serve(URL_A, self.a_text if a_body is None else a_body)
        self.serve(URL_B, self.b_text if b_body is None else b_body)

    def reset(self):
        """Mocks accumulate and the first registered one wins: always clear first."""
        self.vm.clear_mocks()
        self.vm.clear_validators()

    # ----- model -----
    def answers(self, order1, order2):
        """order1 / order2: (winner, quote) for the original and the swapped order."""
        first_of_order1 = re.escape(L.defang(self.a_text)[:100])
        first_of_order2 = re.escape(L.defang(self.b_text)[:100])
        for first, (winner, quote) in ((first_of_order1, order1), (first_of_order2, order2)):
            self.vm.mock_llm(
                r"(?s).*FIRST TEXT START=====\n" + first + r".*",
                json.dumps({"winner": winner, "quote": quote}),
            )

    def honest_prefers_a(self):
        self.answers(("FIRST", A_QUOTE), ("SECOND", A_QUOTE))

    def honest_prefers_b(self):
        self.answers(("SECOND", B_QUOTE), ("FIRST", B_QUOTE))

    # ----- contract helpers -----
    def slots(self, who):
        """open_slots wants an Address; Direct Mode accounts are raw bytes."""
        from genlayer import Address
        return self.c.open_slots(Address(bytes(who)))

    def as_(self, who):
        self.vm.sender = who

    def open(self, label="Test contest", facts=None, prize=1000):
        self.as_(self.organizer)
        return self.c.open_contest(label, json.dumps(FACTS if facts is None else facts), prize)

    def enter(self, cid, who, url, text):
        self.as_(who)
        self.c.submit_entry(cid, url, sha_of(text))

    def ready(self, a_text=None, b_text=None, facts=None):
        """An open contest with both entries submitted and both pages served."""
        if a_text is not None:
            self.a_text = a_text
        if b_text is not None:
            self.b_text = b_text
        cid = self.open(facts=facts)
        self.enter(cid, self.entrant_a, URL_A, self.a_text)
        self.enter(cid, self.entrant_b, URL_B, self.b_text)
        self.serve_entries()
        return cid

    def judge(self, cid, who=None):
        self.as_(self.organizer if who is None else who)
        self.c.judge(cid)

    def judged_a_wins(self):
        """Run one honest, consistent round in which A wins; return the contest id."""
        cid = self.ready()
        self.honest_prefers_a()
        self.judge(cid)
        return cid

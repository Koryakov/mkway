"""Card MW-012, part 1: the gate class in the manifest and the calls log. Synthetic task roots only."""
import json

from _engine import ENGINE
from _mw012 import calls, form_entry, make_root, run, unclassed_entry

FORM = {"owner_ask.edit", "owner_ask.stop", "search",
        "owner_ask.notify", "owner_ask.remind",  # changed by MW-014 (port): the two entries added to the form gate owner_ask
        "lead.edit", "lead.shell", "lead.remind",  # changed by MW-017 (E8): the lead gate is a form gate
        "outbox_check.pre",  # changed by MW-019 (E16): the outbox write gate is class form; its record and reminder are integrity
        "message.send", "message.remind", "message.stop"}  # changed by MW-018 (E12): the message gate is a form gate


def _manifest():
    return json.loads((ENGINE / "manifest.json").read_text(encoding="utf-8"))["entries"]


def test_every_manifest_entry_has_a_class():
    """E1 (rule 1): every manifest entry names `class`, `integrity` or `form`, so every blocking entry has one; the
    form entries are exactly the owner-ask edit and stop entries and the search entry, every other entry (locks,
    subtask, commit checks, delete, records, agents) is integrity. Catches: an entry added with no class, or a lock
    that was marked form."""
    entries = _manifest()
    assert [e["name"] for e in entries if e.get("class") not in ("integrity", "form")] == []
    assert {e["name"] for e in entries if e["class"] == "form"} == FORM
    blocking = [e for e in entries if e.get("function") and e.get("reason_ids")]
    assert blocking and all(e["class"] in ("integrity", "form") for e in blocking)


def test_a_missing_class_reads_integrity():
    """E2 (rule 1): an entry with no `class` key is an integrity gate, so it never degrades; a gate (a profile
    switch) is form only when every entry of it is form. Catches: a default of `form`, which would let a new gate
    degrade without anyone deciding it."""
    import gatemode  # inside the test: a missing module fails this test, not the collection of the file
    bare = unclassed_entry("u1")
    assert gatemode.entry_class(bare) == "integrity"
    assert gatemode.entry_class(form_entry("f1")) == "form"
    mixed = [form_entry("m.a", ), dict(form_entry("m.b"), **{"class": "integrity"})]
    for e in mixed:
        e["gate"] = "m"
    assert gatemode.gate_class(mixed, "m") == "integrity"
    assert gatemode.gate_class([form_entry("f1")], "f1") == "form"
    assert gatemode.gate_class([bare], "u1") == "integrity"
    assert gatemode.gate_class([], "nothing") == "integrity"


def test_the_calls_log_gets_one_row_per_gate_per_call(tmp_path):
    """E3 (rule 2): each gate that runs writes one short row to `<state>/gate_calls.jsonl`: time, gate, verdict
    (`allow`, `refuse`, `log`, `error`); an allowed call and a refused call each leave a row, and a gate the
    profile turns off or whose matcher does not match leaves none. Catches: a log that holds refusals only (no
    denominator for a share), or rows for gates that did not run."""
    root = make_root(tmp_path, gates={"off1": {"on": False}})
    gates = [form_entry("f1"), form_entry("off1"), form_entry("shell1", matcher="Bash")]
    run(root, gates, "src/a.py")
    run(root, gates, "src/bad.py")
    rows = calls(root)
    assert [(r["gate"], r["verdict"]) for r in rows] == [("f1", "allow"), ("f1", "refuse")]
    assert all(set(r) == {"time", "gate", "verdict"} for r in rows)
    assert all(r["time"].endswith("+00:00") and "T" in r["time"] for r in rows)
    assert json.dumps(rows[0]) and len(json.dumps(rows[0])) < 120

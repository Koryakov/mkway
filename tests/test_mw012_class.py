"""Card MW-012, part 1: the gate class in the manifest and the calls log. Synthetic task roots only."""
import json

from _engine import ENGINE
from _mw012 import calls, form_entry, make_root, run, unclassed_entry

FORM = {"owner_ask.remind",  # changed by MW-115 (decisions: MW115-D1, MW115-D1a): the gates owner_ask, outbox_check.pre and search are integrity; the label of owner_ask.remind stays form
        "lead.edit", "lead.shell", "lead.remind",  # changed by MW-017 (E8): the lead gate is a form gate
        "message.send", "message.remind", "message.stop",  # changed by MW-018 (E12): the message gate is a form gate
        "ping.stop"}  # changed by MW-076 (decision: R186): the ping gate is a form gate


def _manifest():
    return json.loads((ENGINE / "manifest.json").read_text(encoding="utf-8"))["entries"]


def test_every_manifest_entry_has_a_class():
    """Checks: every manifest entry has a class, and only the form gates are marked form. E1 rule 1"""
    entries = _manifest()
    assert [e["name"] for e in entries if e.get("class") not in ("integrity", "form")] == []
    assert {e["name"] for e in entries if e["class"] == "form"} == FORM
    blocking = [e for e in entries if e.get("function") and e.get("reason_ids")]
    assert blocking
    assert all(e["class"] in ("integrity", "form") for e in blocking)


def test_a_missing_class_reads_integrity():
    """Checks: a missing class reads as integrity, so a new gate is never form until someone decides it. E2 rule 1"""
    import gatemode  # inside the test: a missing module fails this test, not the collection of the file
    bare = unclassed_entry("u1")
    assert gatemode.entry_class(bare) == "integrity"
    assert gatemode.entry_class(form_entry("f1")) == "form"
    mixed = [dict(form_entry("m.a"), gate="m"), dict(form_entry("m.b"), **{"class": "integrity"}, gate="m")]
    assert gatemode.gate_class(mixed, "m") == "integrity"
    assert gatemode.gate_class([form_entry("f1")], "f1") == "form"
    assert gatemode.gate_class([bare], "u1") == "integrity"
    assert gatemode.gate_class([], "nothing") == "integrity"


def test_the_calls_log_gets_one_row_per_gate_per_call(tmp_path):
    """Checks: the calls log has one row per gate per call, with the time, the gate and the verdict. E3 rule 2"""
    root = make_root(tmp_path, gates={"off1": {"on": False}})
    gates = [form_entry("f1"), form_entry("off1"), form_entry("shell1", matcher="Bash")]
    run(root, gates, "src/a.py")
    run(root, gates, "src/bad.py")
    rows = calls(root)
    assert [(r["gate"], r["verdict"]) for r in rows] == [("f1", "allow"), ("f1", "refuse")]
    assert all(set(r) == {"time", "gate", "verdict", "duration_ms", "session", "event", "tool", "call"} | ({"id", "target", "message", "reason_id"} if r["verdict"] == "refuse" else set()) for r in rows)  # changed by MW-128 (decision: MW128-D1): exact key sets per verdict; was MW-112 (MW112-D3, R4): every row carries duration_ms
    assert all(isinstance(r["duration_ms"], (int, float)) and not isinstance(r["duration_ms"], bool) and r["duration_ms"] >= 0
               for r in rows)  # MW112-D3: the dispatcher writes a rounded float, in milliseconds
    assert all(r["time"].endswith("+00:00") and "T" in r["time"] for r in rows)
    assert json.dumps(rows[0])
    assert len(json.dumps(rows[0])) < 200  # changed by MW-128 (decision: MW128-D1): the row now names its session, event, tool and call; was < 120

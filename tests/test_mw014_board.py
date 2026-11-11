"""Card MW-014, part 3: the board `mkway asks`, the start-block line, the reminder at the next prompt. Synthetic task
roots only; no task data."""
import json

import pytest

import _mw014
from _engine import cli, gate_call, jsonl, task_root
from _mw014 import PAST, write_ask
import dispatch
import records
import register


@pytest.fixture
def task(tmp_path):
    return task_root(tmp_path)


def _row(root, ask_id):
    code, out, err = cli(root, "asks")
    assert code == 0, err
    (line,) = [x for x in out.splitlines() if x.startswith(f"{ask_id} |")]
    return line


def test_the_board_has_one_row_per_ask_file(task):
    """E10: `mkway asks`, from any terminal (the owner's or a session's), prints one row per ask file, oldest first:
    id, card, age, deadline, default, status, blocked part. The card is the one the writing session holds, `not
    established` when no session wrote it. Catches: a board that hides answered asks, shows no age, or names no card."""
    records.append(task / "mkway" / "state", "s1", "take", "CARD-001")
    write_ask(task, "old", session="s1", age_seconds=2 * 3600 + 120, deadline=PAST, default="keep A",
              blocked="part x")
    write_ask(task, "new", age_seconds=300, deadline="none", default="none", blocked="none", reversible="no")
    write_ask(task, "done", status="answered", age_seconds=86400 * 3)
    assert _row(task, "old") == ("old | card CARD-001 | age 2h | deadline 2000-01-01T10:00 | default keep A | "
                                 "status open | blocked part x")
    assert _row(task, "new") == ("new | card not established | age 5m | deadline none | default none | "
                                 "status open | blocked none")
    assert _row(task, "done").startswith("done | card not established | age 3d | ") and "status answered" in _row(
        task, "done")
    for session in (False, True):
        code, out, _err = cli(task, "asks", session=session)
        assert code == 0
        assert [x.split(" |")[0] for x in out.splitlines()] == ["done", "old", "new"]


def test_the_board_with_no_ask_and_with_an_unreadable_one(task):
    """E10: no asks folder or no ask file prints `no ask files`; an ask with a hand-edited bad field is a row that says
    `not established`, never a crash. Catches: a board that fails on the owner's own edit."""
    code, out, _err = cli(task, "asks")
    assert code == 0 and out.strip() == "no ask files"
    (_mw014.asks_folder(task) / "bad_ask.md").write_text("just text\ndeadline: soon\n", encoding="utf-8")
    line = _row(task, "bad")
    assert "default not established" in line and "status not established" in line and "deadline soon" in line


def _context(root, session="s1"):
    payload = {"session_id": session, "hook_event_name": "SessionStart"}
    res = dispatch.run("SessionStart", "start", json.dumps(payload),
                       env={"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"})
    return json.loads(res.stdout)["hookSpecificOutput"]["additionalContext"]


def _asks_line(block):
    (line,) = [x for x in block.splitlines() if x.startswith("open asks:")]
    return line


def test_the_start_block_counts_the_open_asks_with_their_age(task):
    """E11: the start block has `open asks: N (oldest <age>); past deadline: M; defaults taken since the owner's last
    re-seal: K`: N counts the asks with status open, the age is the oldest one's, M those past their deadline, K the
    `ask-default` records at or after the baseline of the owner's last `card resync` (all of them with no baseline).
    Catches: a block that counts answered asks, or a count of defaults that never starts again after a re-seal."""
    assert _asks_line(_context(task)) == ("open asks: 0 (oldest none); past deadline: 0; defaults taken since the "
                                          "owner's last re-seal: 0")
    write_ask(task, "a", age_seconds=2 * 3600 + 60, deadline=PAST)
    write_ask(task, "b", age_seconds=300)
    write_ask(task, "c", status="answered", age_seconds=86400 * 9, deadline=PAST)
    state = task / "mkway" / "state"
    rows = [{"session_id": "s1", "kind": "ask-default", "value": v, "time": t, "by": "session"}
            for v, t in (("x", "2026-01-01T00:00:00.000+00:00"), ("y", "2026-07-01T00:00:00.000+00:00"),
                         ("z", "2026-08-01T00:00:00.000+00:00"))]
    with open(state / "records.jsonl", "a", encoding="utf-8") as fh:
        fh.writelines(json.dumps(r) + "\n" for r in rows)
    assert _asks_line(_context(task)) == ("open asks: 2 (oldest 2h); past deadline: 1; defaults taken since the "
                                          "owner's last re-seal: 3")
    (state / register.BASELINE).write_text(json.dumps({"status": {}, "time": "2026-06-01T00:00:00.000+00:00"}),
                                           encoding="utf-8")
    assert _asks_line(_context(task)).endswith("defaults taken since the owner's last re-seal: 2")


def _prompt(root, session="s1"):
    return gate_call(_mw014.gate().check, root, tool=None, event="UserPromptSubmit", session=session, tool_input=None)


def test_the_reminder_is_for_the_session_that_owns_an_ask_past_its_deadline(task):
    """E12: at the next prompt a session that owns an open ask past its deadline gets a warn `ask-past-deadline` with
    the text «ask <id> is past its deadline: take the default with `mkway ask default <id>` if reversible, else keep
    waiting»; one line for each such ask. No reminder for another session, an ask before its deadline, an ask with no
    deadline, or an ask that is not open. Catches: a reminder to the wrong session, or one that never stops."""
    write_ask(task, "late", session="s1", deadline=PAST)
    write_ask(task, "late2", session="s1", deadline=PAST)
    write_ask(task, "soon", session="s1", deadline=_mw014.FAR)
    write_ask(task, "free", session="s1", deadline="none")
    write_ask(task, "shut", session="s1", deadline=PAST, status="answered")
    write_ask(task, "other", session="s2", deadline=PAST)
    v = _prompt(task)
    assert v.kind == "warn" and v.reason_id == "ask-past-deadline"
    lines = v.message.splitlines()
    assert lines == [f"ask {i} is past its deadline: take the default with `mkway ask default {i}` if reversible, "
                     f"else keep waiting" for i in ("late", "late2")]
    assert _prompt(task, "s2").message.startswith("ask other is past")
    assert _prompt(task, "s3").kind == "allow"
    assert _prompt(task, None).kind == "allow"


def test_the_prompt_group_carries_the_reminder_through_the_dispatcher(tmp_path):
    """E12: through the real manifest the `prompt` group puts the reminder into the prompt's context (entry
    `owner_ask.remind`, `onFailure: none`, no matcher); `gates.owner_ask.on: false` silences it. Catches: a reminder
    that is written but not wired."""
    root = task_root(tmp_path)
    write_ask(root, "late", session="s1", deadline=PAST)
    payload = {"session_id": "s1", "hook_event_name": "UserPromptSubmit", "prompt": "go on"}
    env = {"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"}
    res = dispatch.run("UserPromptSubmit", "prompt", json.dumps(payload), env=env)
    context = json.loads(res.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "[mkway owner_ask.remind ask-past-deadline] ask late is past its deadline" in context
    assert res.exit_code == 0 and json.loads(res.stdout).get("decision") is None
    assert ("owner_ask.remind", "ask-past-deadline") in [(r["gate"], r["reason_id"]) for r in jsonl(
        root / "mkway" / "state" / "refusals.jsonl")]
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    profile["gates"] = {"owner_ask": {"on": False}}
    (root / "mkway" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    assert "late" not in dispatch.run("UserPromptSubmit", "prompt", json.dumps(payload), env=env).stdout
    entry = {e["name"]: e for e in dispatch.load_manifest(dispatch.ENGINE_DIR)}["owner_ask.remind"]
    assert (entry["group"], entry["event"], entry["matcher"], entry["onFailure"], entry["reason_ids"]) == (
        "prompt", "UserPromptSubmit", None, "none", ["ask-past-deadline"])

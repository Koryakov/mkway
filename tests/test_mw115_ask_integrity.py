"""Card MW-115: the three checks of the ask lane, `owner_ask.edit`, `owner_ask.stop` and `outbox_check.pre`, are class
integrity: they refuse from the first install, never start in watch and never trip to watch. `search` stays a form gate.
The Stop gate cannot be wired fail-closed (a crashing Stop hook cannot block): its crash path allows, with a calls-log
error row and a start-line notice. An existing install: the three become hard at once, a stale watch marker is ignored
and the start line names the change once. Everything runs through the real dispatcher on synthetic roots."""
import json

import pytest

from _engine import cli, jsonl, task_root
from _mw012 import seed_calls, write_marker
from _mw014 import ASK_DIR, FAR, ask_text
from _mw019 import OUT, check_text, set_outbox, sha_of, write_doc
from _mw093_install import make_source, make_task
import dispatch
import gate_owner_ask
import install
import startline

WRONG = "0" * 64
USER = {"type": "user", "message": {"content": "a question"}}
SESSION_SOURCES = "kind: session\nchecked: ListAgents\n"
THREE = ("owner_ask.edit", "owner_ask.stop", "outbox_check.pre")


def _entries():
    return json.loads((dispatch.ENGINE_DIR / "manifest.json").read_text(encoding="utf-8"))["entries"]


def _state(root):
    return root / "mkway" / "state"


def _installed(tmp_path):
    """A task root after a real first install (vcs none), with the outbox folder and one checker type in its profile."""
    task = make_task(tmp_path, vcs="none")
    install.install(task, make_source(tmp_path, vcs="none"), vcs="none")
    set_outbox(task, dir=OUT, checkers=["critic"])
    (task / OUT).mkdir(exist_ok=True)
    return task


def _hook(root, event, group, **payload):
    body = {"session_id": "s1", "hook_event_name": event, "cwd": str(root), **payload}
    mine = [e for e in dispatch.load_manifest(dispatch.ENGINE_DIR) if e["name"] in THREE]  # only the three entries
    return dispatch.run(event, group, json.dumps(body), env={"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"},
                        manifest=mine)


def _write(root, rel, content):
    """One Write through the hook; a Write that the hook lets through is carried out, as the tool would."""
    result = _hook(root, "PreToolUse", "edit", tool_name="Write", tool_input={"file_path": rel, "content": content})
    if result.stdout == "":
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(content, encoding="utf-8")
    return result


def _transcript(tmp_path, entries):
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return str(path)


def _stop(root, tmp_path, entries):
    return _hook(root, "Stop", "stop", stop_hook_active=False, transcript_path=_transcript(tmp_path, entries),
                 last_assistant_message="Request: x")


def _wrote_ask(root):
    rel = f"{ASK_DIR}/t_ask.md"
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Write",
                                                          "input": {"file_path": str(root / rel), "content": "x"}}]}}


def _reason(result):
    """The text the hook gave for a refusal: a deny reason (edit) or a block reason (Stop); '' when it allowed."""
    if not result.stdout:
        return ""
    data = json.loads(result.stdout)
    return data.get("reason") or data.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")


def _refuse_outbox(root, tmp_path):
    write_doc(root)
    return _write(root, f"{OUT}/a.md.check.md", check_text(WRONG))


def _refuse_edit(root, tmp_path):
    return _write(root, f"{ASK_DIR}/t_ask.md", ask_text())


def _refuse_stop(root, tmp_path):
    return _stop(root, tmp_path, [USER])


def _kinds(root):
    return [r["kind"] for r in jsonl(_state(root) / "refusals.jsonl") if r.get("kind") in ("refuse", "would-refuse")]


# ---- the class -------------------------------------------------------------------------------------------------------

def test_the_ask_lane_checks_and_search_are_integrity():
    """Checks: the raw manifest names class integrity for the edit check, the Stop check, the outbox write check and the
    owner record (K8, R287a) and the search check (K7, R287c): a gate with a kind row is integrity. The label of the
    reminder, whose only reason is a record row, stays form."""
    by_name = {e["name"]: e["class"] for e in _entries()}
    assert {n: by_name[n] for n in (*THREE, "owner_ask.notify", "search", "owner_ask.remind")} == {
        "owner_ask.edit": "integrity", "owner_ask.stop": "integrity", "outbox_check.pre": "integrity",
        "owner_ask.notify": "integrity", "search": "integrity", "owner_ask.remind": "form"}


def test_a_fresh_install_writes_no_marker_and_no_install_row_for_the_ask_lane_and_search(tmp_path):
    """Catches: a first install that puts the ask lane or the search check in watch, so it only logs until the owner
    runs `gate on`: no marker and no install row for the owner_ask gate, the outbox write gate and the search gate, while
    a form gate (message) still starts in watch."""
    task = _installed(tmp_path)
    names = {p.name for p in (_state(task) / "gate_mode").iterdir()}
    installed = {r["gate"] for r in jsonl(_state(task) / "refusals.jsonl") if r["reason_id"] == "gate-watch-installed"}
    gates = {"owner_ask", "outbox_check.pre", "search", "message"}
    assert (names & {f"{g}.watch" for g in gates}, installed & gates) == ({"message.watch"}, {"message"})


# ---- refuse from the first install, and the way out ------------------------------------------------------------------

def test_a_fresh_install_refuses_a_stale_check_write_and_the_right_sha_is_the_way_out(tmp_path):
    """Catches: the outbox write check that only logs after a first install; the refusal is a deny, and a write with the
    document's real sha passes."""
    task = _installed(tmp_path)
    write_doc(task)
    refused = _write(task, f"{OUT}/a.md.check.md", check_text(WRONG))
    assert "[mkway outbox_check.pre check-sha-mismatch]" in _reason(refused)
    assert _kinds(task) == ["refuse"]
    assert _write(task, f"{OUT}/a.md.check.md", check_text(sha_of(task / OUT / "a.md"))).stdout == ""


def test_a_fresh_install_refuses_an_ask_without_sources_and_the_sources_file_is_the_way_out(tmp_path):
    """Catches: the ask edit check that only logs after a first install; the refusal names the sources file, and once
    that file is written the same write passes."""
    task = _installed(tmp_path)
    refused = _write(task, f"{ASK_DIR}/t_ask.md", ask_text())
    assert "[mkway owner_ask.edit ask-sources-missing]" in _reason(refused)
    assert "t_sources.md" in _reason(refused)
    assert _kinds(task) == ["refuse"]
    assert _write(task, f"{ASK_DIR}/t_sources.md", SESSION_SOURCES).stdout == ""
    assert _write(task, f"{ASK_DIR}/t_ask.md", ask_text()).stdout == ""


def test_a_fresh_install_blocks_a_final_reply_with_no_ask_and_writing_the_ask_is_the_way_out(tmp_path):
    """Catches: the Stop check that only logs after a first install; the reply is blocked, and once the ask file is on
    disk the same reply passes."""
    task = _installed(tmp_path)
    refused = _stop(task, tmp_path, [USER])
    assert "[mkway owner_ask.stop ask-not-written]" in _reason(refused)
    assert _kinds(task) == ["refuse"]
    (task / ASK_DIR).mkdir(parents=True, exist_ok=True)
    (task / ASK_DIR / "t_ask.md").write_text(ask_text(), encoding="utf-8")
    assert _stop(task, tmp_path, [USER, _wrote_ask(task)]).stdout == ""


def test_a_fresh_install_refuses_a_question_with_no_search_and_a_search_record_is_the_way_out(tmp_path):
    """Catches: the search check that only logs after a first install (R287c: it is integrity); a question after no
    search is denied with the command to run, and once the search is recorded the same question passes."""
    task = _installed(tmp_path)
    profile = json.loads((task / "mkway" / "profile.json").read_text(encoding="utf-8"))
    profile["owner_ask"] = {"tool_allowed": True}
    (task / "mkway" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    ask = {"tool_name": "AskUserQuestion", "tool_input": {"questions": []},
           "transcript_path": _transcript(tmp_path, [dict(USER, timestamp="2026-11-10T12:00:00.000Z")])}
    mine = [e for e in dispatch.load_manifest(dispatch.ENGINE_DIR) if e["name"] == "search"]
    body = {"session_id": "s1", "hook_event_name": "PreToolUse", "cwd": str(task), **ask}
    env = {"CLAUDE_PROJECT_DIR": str(task), "CLAUDECODE": "1"}
    refused = dispatch.run("PreToolUse", "edit", json.dumps(body), env=env, manifest=mine)
    assert "[mkway search search-missing]" in _reason(refused)
    assert _kinds(task) == ["refuse"]
    row = {"session_id": "s1", "kind": "search", "value": "S-1", "time": "2026-11-10T12:00:30.000+00:00", "by": "session"}
    (_state(task) / "records.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert dispatch.run("PreToolUse", "edit", json.dumps(body), env=env, manifest=mine).stdout == ""


# ---- no trip ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("gate, stimulus", [("owner_ask", _refuse_edit), ("owner_ask", _refuse_stop),
                                            ("outbox_check.pre", _refuse_outbox)],
                         ids=["owner_ask.edit", "owner_ask.stop", "outbox_check.pre"])
def test_a_run_of_refusals_never_trips_the_check_into_watch(tmp_path, gate, stimulus):
    """Catches: the trip rule (20 calls, a refusal share above a third) putting an ask-lane check into watch: after 30
    refusals in the log, the next refusal is still a deny and no marker is written."""
    task = _installed(tmp_path)
    seed_calls(task, gate, refuse=30)
    refused = stimulus(task, tmp_path)
    assert _reason(refused) != ""
    assert (task / "mkway" / "state" / "gate_mode" / f"{gate}.watch").is_file() is False


# ---- a stale marker of an existing install ---------------------------------------------------------------------------

def test_a_marker_of_an_old_install_does_not_soften_the_outbox_check_and_the_start_line_names_the_change_once(tmp_path):
    """Catches: an existing install whose watch marker keeps the outbox write check soft: it refuses at once, the start
    line says the gate was in watch and now refuses, and the second start line does not repeat it."""
    task = _installed(tmp_path)
    write_marker(task, "outbox_check.pre", cause="installed")
    write_doc(task)
    assert "check-sha-mismatch" in _reason(_write(task, f"{OUT}/a.md.check.md", check_text(WRONG)))
    profile = json.loads((task / "mkway" / "profile.json").read_text(encoding="utf-8"))
    manifest = dispatch.load_manifest(dispatch.ENGINE_DIR)
    first = startline.render(task, task / "mkway" / "profile.json", profile, [], manifest)
    second = startline.render(task, task / "mkway" / "profile.json", profile, [], manifest)
    named = [line for line in first.splitlines() if line.startswith("changed: gate outbox_check.pre")]
    anchor = [line for line in first.splitlines() if line.startswith("gate message: WATCH")]  # the format of a watch line
    soft = [line for line in (first + "\n" + second).splitlines() if line.startswith("gate outbox_check.pre")]
    again = [line for line in second.splitlines() if "outbox_check.pre" in line and ("WATCH" in line or "changed:" in line)]
    assert (len(named), "refuses" in named[0], len(anchor), soft, again) == (1, True, 1, [], [])


def test_an_ask_written_in_watch_without_sources_is_refused_at_its_next_edit_with_the_sources_file_as_way_out(tmp_path):
    """Catches: an ask file written while the edit check was in watch, with no sources file, that stays editable on an
    upgraded install: its next edit is refused and the text names the sources file."""
    task = _installed(tmp_path)
    write_marker(task, "owner_ask", cause="installed")
    (task / ASK_DIR).mkdir(parents=True, exist_ok=True)
    (task / ASK_DIR / "t_ask.md").write_text(ask_text(), encoding="utf-8")
    edit = {"file_path": f"{ASK_DIR}/t_ask.md", "old_string": "status: open", "new_string": "status: open"}
    refused = _hook(task, "PreToolUse", "edit", tool_name="Edit", tool_input=edit)
    assert "[mkway owner_ask.edit ask-sources-missing]" in _reason(refused)
    assert "t_sources.md" in _reason(refused)
    assert _write(task, f"{ASK_DIR}/t_sources.md", SESSION_SOURCES).stdout == ""
    assert _hook(task, "PreToolUse", "edit", tool_name="Edit", tool_input=edit).stdout == ""


# ---- the Stop crash path ---------------------------------------------------------------------------------------------

def test_a_crash_of_the_stop_check_allows_with_an_error_row_and_a_start_line_notice(tmp_path, monkeypatch):
    """Catches: a crashing Stop check that blocks (it cannot: Claude Code ends the turn after eight blocks in a row) or
    that crashes unseen: the reply goes through, the calls log has an error row, the refusal log has a gate-error row and
    the start line names the Stop gate that failed."""
    def _boom(ctx):
        raise OSError("disk")
    monkeypatch.setattr(gate_owner_ask, "_stop", _boom)
    task = _installed(tmp_path)
    result = _stop(task, tmp_path, [USER])
    calls = jsonl(_state(task) / "gate_calls.jsonl")
    errors = [r for r in jsonl(_state(task) / "refusals.jsonl") if r["reason_id"] == "gate-error"]
    profile = json.loads((task / "mkway" / "profile.json").read_text(encoding="utf-8"))
    context = startline.render(task, task / "mkway" / "profile.json", profile, [],
                               dispatch.load_manifest(dispatch.ENGINE_DIR))
    notice = [line for line in context.splitlines() if line.startswith("Stop gate owner_ask.stop")]
    assert (result.exit_code, "decision" in result.stdout, [r["verdict"] for r in calls],
            [(r["gate"], r["applied"]) for r in errors], len(notice)) == (0, False, ["error"],
                                                                         [("owner_ask.stop", "allow")], 1)
    assert "allowed" in notice[0]


# ---- the owner's switch on an integrity gate -------------------------------------------------------------------------

def test_the_owner_cannot_put_the_outbox_check_in_watch_and_the_refusal_names_a_form_gate_as_the_way_out(tmp_path):  # D2
    """Checks: `gate watch outbox_check.pre` is refused gate-watch-integrity, the text names what to do instead, and
    that named command, `gate watch message`, is accepted."""
    root = task_root(tmp_path)
    code, _out, err = cli(root, "gate", "watch", "outbox_check.pre")
    assert (code, "gate-watch-integrity" in err, "mkway gate watch message" in err) == (1, True, True)
    assert cli(root, "gate", "watch", "message")[0] == 0

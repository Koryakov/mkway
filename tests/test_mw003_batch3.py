"""Batch 3 of card MW-003 (the batch-2 close check's ruled items H1, H4, H5, M1; R54, R55). Synthetic task roots only;
a session's command runs as `cli(..., session=True)`, a gate as the dispatcher calls it."""
import json

import pytest

from _engine import cli, gate_call, task_root
from test_cardmoves import _row, set_paths
import gate_lock
import records

P = "python mkway/engine/mkway.py"


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _shell(root, command, tool="Bash", session="s1"):
    v = gate_call(gate_lock.check, root, tool=tool, tool_input={"command": command}, session=session)
    return v.reason_id if v.kind == "refuse" else "allow"


@pytest.fixture
def task(tmp_path):
    root = task_root(tmp_path)
    assert cli(root, "card", "new", "First", session=True)[0] == 0
    set_paths(root, "CARD-001", "`src/a.py`")
    assert cli(root, "card", "open", "CARD-001")[0] == 0
    records.append(root / "mkway" / "state", "s1", "take", "CARD-001")
    assert cli(root, "card", "set", "CARD-001", "waiting", session=True)[0] == 0
    set_paths(root, "CARD-001", "`src/`, `other/`")  # the card file is exempt: the holder widens its own scope
    return root


def test_reopen_from_waiting_never_writes_paths_with_the_signal_stripped(task):
    """Checks: a reopen from waiting keeps the Paths the first open recorded, whatever the caller's environment says. H1 route a, R54"""
    # the holder strips CLAUDECODE and runs card set id open from waiting; the card reopens but its recorded Paths stay
    # the ones the first open recorded.
    assert cli(task, "card", "set", "CARD-001", "open")[0] == 0  # no session signal: looks like the owner
    assert _row(task, "CARD-001")["status"] == "open"
    assert _row(task, "CARD-001")["paths"] == "src/a.py"


def test_reopen_from_waiting_never_writes_paths_with_a_chosen_profile(task, tmp_path):
    """Checks: a reopen from waiting keeps the Paths the first open recorded, whatever profile the caller names. H1 route b, R54"""
    # the holder keeps the signal and passes --profile naming a copy of the profile with cards.owner_moves: []; the reopen
    # still writes no Paths, and neither does the owner's card open from waiting.
    evil = tmp_path / "evil.json"
    evil.write_text(json.dumps(dict(_profile(task), cards={"owner_moves": []})), encoding="utf-8")
    assert cli(task, "card", "set", "CARD-001", "open", "--profile", str(evil), session=True)[0] == 0
    assert _row(task, "CARD-001")["paths"] == "src/a.py"
    assert cli(task, "card", "set", "CARD-001", "waiting", session=True)[0] == 0
    assert cli(task, "card", "open", "CARD-001")[0] == 0
    assert _row(task, "CARD-001")["paths"] == "src/a.py"


DENY = [
    ("Bash", f"unset CLAUDECODE; {P} card $'open' CARD-001"),
    ("Bash", f"{P} lock $'open' engine"),
    ("Bash", f"{P} card set CARD-001 $'closed'"),
    ("Bash", f"{P} card release CARD-001 $'--force'"),
    ("Bash", f"{P} card {{open,}} CARD-001"),
    ("Bash", f"{P} $'card' open"),
    ("PowerShell", f"$env:CLAUDECODE=''; {P} card ('op'+'en') CARD-001"),
    ("PowerShell", f'{P} card "op$()en" CARD-001'),
    ("Bash", f"unset CLAUDECODE; {P} card list"),
    ("Bash", f"env -u CLAUDECODE {P} card list"),
    ("PowerShell", f"$env:CLAUDECODE=''; {P} card list"),
    ("Bash", f"{P} card $'take' CARD-001"),
    ("Bash", f"{P} card list | cat"),
    ("Bash", f"{P} card list > out.txt"),
    ("Bash", f"{P} card list --profile x.json"),
    ("Bash", f"{P} card list --root x"),
    ("Bash", f"X=1 {P} card list"),
    ("Bash", f"nohup {P} card list"),
    ("Bash", f"timeout 5 {P} card list"),
    ("Bash", f"cd /tmp && {P} card list"),
]


@pytest.mark.parametrize("tool,command", DENY)
def test_engine_call_not_in_exact_form_is_refused(task, tool, command):
    """Catches: an owner-only command spelled so the gate reads another word than the shell runs, or a call that strips the session signal first. H4, R54"""
    # a command that holds an engine call passes only as the one plain call, optionally after cd <path inside the bundle
    # root> &&: no other segment, pipe, redirect, VAR= prefix or wrapper; no $, backtick, {, [, (, * or ? in the call; no
    # --profile or --root.
    assert _shell(task, command, tool=tool) == "engine-call-not-plain", command


@pytest.mark.parametrize("tool,command", [
    ("Bash", f"{P} card list"),
    ("Bash", "cd mkway/engine && python mkway.py card list"),
    ("Bash", f'{P} card new "two words"'),
    ("PowerShell", f"{P} card list"),
])
def test_engine_call_in_exact_form_passes(task, tool, command):
    """Checks: the plain call, the cd bundle root form and a quoted whole-word argument holding a space pass. H4 allow side, R55 E1"""
    # the exact-form rule must not over-refuse the parser's plain quote pair.
    assert _shell(task, command, tool=tool) == "allow", command


FORGED_LOCK = '{"name": "engine", "state": "open", "opened_at": "2026-01-01T00:00:00", "until": "2099-01-01T00:00:00"}'
FOLDER_DENY = [
    ("Bash", f"cd mkway/locks && echo '{FORGED_LOCK}' > engine.json", "lock-file-by-session"),
    ("Bash", "cd mkway/state; echo abc > register.sha", "lock-closed-shell"),
    ("Bash", "pushd mkway/state && echo x >> records.jsonl", "lock-closed-shell"),
    ("Bash", "cd mkway && cd state && echo x > register.sha", "lock-closed-shell"),
    ("Bash", "git -C mkway checkout -- cards/REGISTER.md", "lock-closed-shell"),
    # changed by list item 5 (R43, H5 «then R43 applies»): an unreadable folder makes the write `everywhere`; it is
    # refused when the text names a closed target (here `mkway.lock`), else logged
    ("Bash", "cd $D && echo x > mkway.lock", "lock-closed-shell"),
    ("PowerShell", "mi C:/tmp/x mkway/locks/engine.json", "lock-file-by-session"),
    ("PowerShell", "cpi C:/tmp/x mkway/state/register.sha", "lock-closed-shell"),
    ("PowerShell", "Set-Content -Pa mkway/state/register.sha -Value x", "lock-closed-shell"),
    ("PowerShell", "Set-Content -LP mkway/state/register.sha -Value x", "lock-closed-shell"),
    ("PowerShell", "Set-Content -Path:mkway/state/register.sha -Value x", "lock-closed-shell"),
    ("PowerShell", "Push-Location mkway/locks; 'x' > engine.json", "lock-file-by-session"),
    ("PowerShell", "Set-Location -Path mkway/state; 'x' > register.sha", "lock-closed-shell"),
]


@pytest.mark.parametrize("tool,command,reason", FOLDER_DENY)
def test_writes_follow_folder_changes_and_aliases(task, tool, command, reason):
    """Catches: a forged lock file or seal written after a folder change, or through an alias, that the gate reads as a harmless relative path. H5, R54"""
    # shell_writes follows cd, pushd, Set-Location, Push-Location and git -C; a folder change to a target it cannot read
    # makes a relative write everywhere; the PowerShell aliases mi, cpi and the parameter prefixes -Pa, -LP, -Path: are read.
    assert _shell(task, command, tool=tool) == reason, command


def test_forged_lock_after_cd_leaves_the_engine_closed(task):
    """Catches: a session that opens a lock for itself through a folder change. H5"""
    # the forged locks/engine.json written after cd mkway/locks is refused, so an Edit of the engine's own code stays refused.
    assert _shell(task, f"cd mkway/locks && echo '{FORGED_LOCK}' > engine.json") == "lock-file-by-session"
    v = gate_call(gate_lock.check, task, tool="Edit", tool_input={"file_path": "mkway/engine/gate_lock.py"})
    assert v.kind == "refuse"
    assert v.reason_id == "lock-closed-edit"


@pytest.mark.parametrize("tool,command", [
    ("Bash", "(cd mkway/locks); echo x > engine.json"),
    ("Bash", "cd mkway && echo x > notes.txt"),
    ("Bash", "cd src && echo x > a.txt"),
    ("PowerShell", "Push-Location src; 'x' > a.txt; Pop-Location"),
])
def test_folder_changes_that_reach_no_target_pass(task, tool, command):
    """Checks: a folder change that reaches no lock target passes, and a subshell cd ends with the subshell. H5 allow side"""
    # the catch this allow side guards is a folder rule that refuses every cd.
    assert _shell(task, command, tool=tool) == "allow", command


@pytest.mark.parametrize("make_cwd", [
    pytest.param(lambda task: None, id="no-cwd"),
    pytest.param(lambda task: str(task.parent / "elsewhere"), id="outside-root"),
])
def test_payload_cwd_is_the_start_folder(task, make_cwd):
    """Catches: a gate that takes the root as the folder of every command. Item 15, R58 d"""
    # the gate starts the folder tracking from the hook input's cwd, so cd mkway/locks in one call and echo x > engine.json
    # in the next is refused. A cwd that is missing or outside the root makes a relative write everywhere.
    locks = str(task / "mkway" / "locks")
    v = gate_call(gate_lock.check, task, tool="Bash", tool_input={"command": "echo x > engine.json"}, cwd=locks)
    assert v.kind == "refuse"
    assert v.reason_id == "lock-file-by-session"
    import dispatch
    cwd = make_cwd(task)
    ctx = dispatch.make_context(profile=_profile(task), root=task, session_id="s1", event="PreToolUse", gate="g",
                                tool_name="Bash", tool_input={}, budget_seconds=None, once=lambda t: True,
                                env={}, cwd=cwd)
    assert ctx.shell_writes("echo x > out.txt").everywhere, cwd
    assert not ctx.shell_writes("echo x > /abs/out.txt").everywhere, cwd


def forge_status(root, card_id, was, now):
    """A coordinated forge (the decided limit of R19a): the register and its seal written together, no record."""
    import hashlib
    reg = root / "mkway" / "cards" / "REGISTER.md"
    text = reg.read_text(encoding="utf-8")
    line = next(x for x in text.splitlines() if x.startswith(f"| {card_id} |"))
    reg.write_bytes(text.replace(line, line.replace(f"| {was} |", f"| {now} |")).encode("utf-8"))
    (root / "mkway" / "state" / "register.sha").write_text(hashlib.sha256(reg.read_bytes()).hexdigest(),
                                                            encoding="utf-8")


def _session_start(root, source="startup"):
    import dispatch
    payload = {"session_id": "s9", "hook_event_name": "SessionStart", "source": source, "cwd": str(root)}
    res = dispatch.run("SessionStart", "start", json.dumps(payload),
                       env={"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"})
    return json.loads(res.stdout) if res.stdout else {}


@pytest.fixture
def two_cards(tmp_path):
    root = task_root(tmp_path)
    for title in ("One", "Two"):
        assert cli(root, "card", "new", title, session=True)[0] == 0
    assert cli(root, "card", "resync")[0] == 0  # the owner's re-seal sets the baseline
    assert cli(root, "card", "open", "CARD-001")[0] == 0
    forge_status(root, "CARD-002", "proposed", "open")
    return root


def _change_lines(root, sources):
    """The «card changes since» line of each session start, in the order the sources are given, on one root."""
    lines = []
    for source in sources:
        context = _session_start(root, source)["hookSpecificOutput"]["additionalContext"]
        (line,) = [x for x in context.splitlines() if x.startswith("card changes since")]
        lines.append(line)
    return lines


def test_start_and_compaction_never_move_the_baseline(two_cards):
    """Checks: a start, a compaction and a second start each show the card changes since the owner's re-seal, and only the re-seal moves the baseline. M1, R54"""
    # the card changes are counted from the owner's last re-seal (card resync); a start or a compaction shows them and
    # never moves the baseline; the re-seal does. One root, one sequence: startup, compact, startup, then resync, startup.
    want = ["CARD-001 proposed -> open (open by owner)", "CARD-002 proposed -> open (no record)"]
    first, compact, again = _change_lines(two_cards, ["startup", "compact", "startup"])
    assert all(w in line for w in want for line in (first, compact, again))
    assert cli(two_cards, "card", "resync")[0] == 0
    (last,) = _change_lines(two_cards, ["startup"])
    assert last.endswith("none")


def test_owner_sees_unrecorded_changes_and_owner_moves(two_cards):
    """Checks: the unrecorded card changes and the owner-only moves since the baseline reach the owner as systemMessage and stay in additionalContext. M1, R54, R60"""
    # the changes with no record and the owner-only moves since the baseline go to the owner as systemMessage and stay in
    # additionalContext.
    out = _session_start(two_cards)
    shown = out.get("systemMessage") or ""
    assert "CARD-002 proposed -> open (no record)" in shown
    assert "CARD-001 proposed -> open (open by owner)" in shown
    assert "CARD-002 proposed -> open (no record)" in out["hookSpecificOutput"]["additionalContext"]
    assert cli(two_cards, "card", "resync")[0] == 0
    assert "systemMessage" not in _session_start(two_cards)

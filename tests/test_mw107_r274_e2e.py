"""Card MW-107 (ruling R274 and R274a): the write-outside rule through the REAL hook command lines of an installed engine
(stdin JSON in, exit code and permissionDecision out): the incident replay, the same file inside the root, a listed folder, a
linked checkout below the root, the owner's addition counted at the next call with no restart, the start line, and the wiring
of the three entries that carry the rule. The fake home is the one the hook driver sets (`<base>/home`). Synthetic names only."""
import json
import os

import pytest

from _engine import REPO
from _hook_driver import decision, install_project

pytestmark = pytest.mark.engine_repo

CLI = "python mkway/engine/mkway.py"
LEAD, OTHER = "L1", "n1"
EDIT_TOOLS = "Edit|Write|MultiEdit|NotebookEdit"
SHELL_TOOLS = "Bash|PowerShell"


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    p = install_project(tmp_path_factory.mktemp("r274"))
    for session in (LEAD, OTHER):
        decision(p.fire("SessionStart", session))
    p.session_shell(LEAD, f"{CLI} lead register")
    return p


def write_decision(p, session, path):
    return decision(p.fire("PreToolUse", session, "Write", {"file_path": str(path), "content": "x"}))


def shell_decision(p, session, command):
    return decision(p.fire("PreToolUse", session, "Bash", {"command": command}))


def test_the_incident_replay_a_write_by_the_sibling_checkouts_absolute_path_is_refused(proj):
    """Catches: R274 5.9, the real case: an edit-tool write by the absolute path of a sibling checkout of the project (a folder holding its own .git) that the real hook lets through."""
    sibling = proj.base / "sibling"
    (sibling / ".git").mkdir(parents=True)
    got = write_decision(proj, OTHER, sibling / "conftest.py")
    assert (got.kind, got.reason_id, got.gate) == ("deny", "write-outside-root", "outside.edit")  # R274e: the session check is its own gate
    assert str(proj.root.resolve()).replace("\\", "/") in got.text or os.path.realpath(proj.root).replace("\\", "/") in got.text


def test_the_same_file_inside_the_root_is_not_refused_by_the_outside_rule(proj):
    """Checks: the nearest allow of the replay, the card file of a new card inside the root is a file every session writes."""
    got = write_decision(proj, OTHER, proj.root / "mkway" / "cards" / "CARD-099-x" / "CARD.md")
    assert got.kind == "allow"


def test_a_listed_outside_folder_is_allowed(proj):
    """Checks: a path of the shipped list (the harness plans folder under the home) is allowed for a session that is no lead."""
    got = write_decision(proj, OTHER, proj.base / "home" / ".claude" / "plans" / "a.md")
    assert got.kind == "allow"


def test_a_shell_redirect_outside_is_refused_and_one_inside_the_root_is_not_judged_by_it(proj):
    """Catches: R274 5.9, a shell redirect to an outside path that passes; and a redirect to a root path that the outside rule refuses."""
    outside = shell_decision(proj, OTHER, f"echo x > {(proj.base / 'sibling' / 'conftest.py').as_posix()}")
    inside = shell_decision(proj, OTHER, "echo x > mkway/cards/CARD-099-x/CARD.md")
    assert ((outside.kind, outside.reason_id, outside.gate), inside.reason_id) == (("deny", "write-outside-root", "outside.shell"), None)


@pytest.fixture(scope="module")
def nested(proj):
    """A linked checkout of the project repository below its root (another session's worktree)."""
    proj.git("worktree", "add", "-q", str(proj.root / "nested-wt"), "-b", "r274-nested")
    return proj.root / "nested-wt"


def test_a_linked_checkout_below_the_root_is_outside_for_the_real_hook(proj, nested):
    """Catches: R274 5.9, a session at one checkout that writes into a linked checkout of the same repository nested below its root, and the real hook lets it through; a plain folder there is judged by the card rule."""
    refused = write_decision(proj, OTHER, nested / "src" / "a.py")
    plain = write_decision(proj, OTHER, proj.root / "plain-folder" / "a.py")
    assert ((refused.kind, refused.reason_id), (plain.kind, plain.reason_id)) == (
        ("deny", "write-outside-root"), ("deny", "no-open-card"))


def test_the_way_out_of_a_write_into_another_checkout_works_through_the_real_hook(proj, nested):
    """Catches: R274a 8.4, a refusal of a write into another session's checkout whose named way out is not proven: refused, its text names the orderer's own checkout and `mkway send`, the brief written in the own checkout is allowed, and the send call is no write position."""
    refused = write_decision(proj, OTHER, nested / "ORDER.md")
    brief_inside = write_decision(proj, OTHER, proj.root / "mkway" / "cards" / "CARD-099-x" / "CARD.md")
    sent = shell_decision(proj, OTHER, f"{CLI} send lead-1 --file mkway/cards/CARD-099-x/CARD.md")
    assert (refused.kind, refused.reason_id, "the orderer's own checkout" in refused.text, "`mkway send`" in refused.text,
            brief_inside.kind, sent.reason_id) == ("deny", "write-outside-root", True, True, "allow", None)


def test_an_owner_addition_counts_at_the_next_call_with_no_restart(proj):
    """Catches: R274a 8.8, a profile addition to `paths.outside_writable` that waits for a new session: the hook reads the profile at each call."""
    target = proj.base / "data-folder" / "a.csv"
    before = write_decision(proj, OTHER, target)
    file = proj.root / "mkway" / "profile.json"
    original = file.read_text(encoding="utf-8")
    profile = json.loads(original)
    profile["paths"] = {**profile.get("paths", {}), "outside_writable": [(proj.base / "data-folder").as_posix() + "/**"]}
    file.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    try:
        after = write_decision(proj, OTHER, target)
    finally:
        file.write_text(original, encoding="utf-8")
    assert ((before.kind, before.reason_id), after.kind) == (("deny", "write-outside-root"), "allow")


def test_the_start_block_names_the_root(proj):
    """Catches: R274 5.8, a session start with no sentence naming the root every path it writes starts at."""
    fired = proj.fire("SessionStart", "n2")
    contexts = [r.json["hookSpecificOutput"]["additionalContext"] for r in fired.runs
                if r.json and isinstance(r.json.get("hookSpecificOutput"), dict)
                and "additionalContext" in r.json["hookSpecificOutput"]]
    root = os.path.realpath(proj.root).replace("\\", "/")
    assert any(f"root: {root}; every path you write starts here" in c.splitlines() for c in contexts)


def manifest_entries() -> list:
    return json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]


@pytest.mark.parametrize("name, matcher", [("outside.edit", EDIT_TOOLS), ("outside.shell", SHELL_TOOLS),
                                           ("lead.edit", EDIT_TOOLS), ("lead.shell", SHELL_TOOLS)])
def test_the_four_entries_that_carry_the_rule_are_wired_to_every_write_tool_and_fail_closed(name, matcher):
    """Checks: R274 5.9, the hook wiring row: the matcher holds every edit tool (or both shell tools), a crash or a timeout refuses (`onFailure: block`), the timeout is 10 seconds."""
    (entry,) = [e for e in manifest_entries() if e["name"] == name]
    assert (entry["event"], entry["matcher"], entry["onFailure"], entry["timeout"], entry["status"]) == (
        "PreToolUse", matcher, "block", 10, "on")
    assert "write-outside-root" in entry["reason_ids"]


@pytest.mark.parametrize("name", ["outside.edit", "outside.shell"])
def test_the_session_outside_check_is_an_integrity_gate_of_its_own(name):
    """Catches: R274a 8.6 and R274e, the session outside check inside a form gate (watch mode on a first install, so not hard from install): the entry is of class integrity, of its own gate `outside`, declares only the outside reason, and the subtask gate no longer declares it."""
    import gatemode
    entries = manifest_entries()
    (entry,) = [e for e in entries if e["name"] == name]
    (subtask,) = [e for e in entries if e["name"] == "subtask"]
    assert (entry["class"], entry["gate"], entry["reason_ids"], gatemode.gate_class(entries, "outside"),
            "write-outside-root" in subtask["reason_ids"]) == ("integrity", "outside", ["write-outside-root"], "integrity", False)


def test_the_session_outside_check_comes_after_the_lock_check_in_both_groups():
    """Checks: R274e, the order of the gates: the lock check runs first, the outside check next, in the edit group and in the shell group."""
    names = [e["name"] for e in manifest_entries()]
    assert (names.index("lock.edit") < names.index("outside.edit") < names.index("subtask"),
            names.index("lock.shell") < names.index("outside.shell") < names.index("delete")) == (True, True)


@pytest.fixture(scope="module")
def hard(tmp_path_factory):
    """A second installed project whose lead gate is switched off and then put in watch mode: the integrity gate must not care."""
    p = install_project(tmp_path_factory.mktemp("r274hard"))
    decision(p.fire("SessionStart", OTHER))
    return p


@pytest.mark.parametrize("mode", ["off", "watch"])
def test_the_session_outside_check_is_hard_whatever_the_lead_gate_mode(hard, mode):
    """Catches: R274a 8.6, a session shell write outside the root that passes while the form gate `lead` is off or in watch mode: the check is hard from install, on purpose (K1), no watch date."""
    hard.owner("gate", mode, "lead")
    got = shell_decision(hard, OTHER, f"echo x > {(hard.base / 'sibling' / 'conftest.py').as_posix()}")
    assert (got.kind, got.reason_id, got.gate) == ("deny", "write-outside-root", "outside.shell")


def outside_target(p) -> str:
    return (p.base / "sibling" / "conftest.py").as_posix()


def test_a_delete_word_does_not_switch_the_outside_check_off(proj):
    """Catches: R274e (3), a compound command that names a delete program and then writes outside the root, which passes because the whole command is left to the delete gate."""
    got = shell_decision(proj, OTHER, f"rm a.txt; echo x > {outside_target(proj)}")
    assert (got.kind, got.reason_id, got.gate) == ("deny", "write-outside-root", "outside.shell")


def test_a_delete_of_an_outside_file_alone_is_left_to_the_delete_gate(proj):
    """Checks: the other half of R274e (3), the delete program's own target is the delete gate's: `delete-outside-root`, never the outside reason."""
    got = shell_decision(proj, OTHER, f"rm {outside_target(proj)}")
    assert (got.kind, got.reason_id) == ("deny", "delete-outside-root")


PASSING_SHAPES = [
    pytest.param('echo "a > {e}/x.txt"', id="a-quoted-redirect-sign"),
    pytest.param("cat <<'EOF'\nline > {e}/x.txt\nEOF", id="a-heredoc-body"),
    pytest.param('echo "see {e}/x.txt"', id="a-path-in-a-message"),
    pytest.param("echo x >/dev/null", id="redirect-to-dev-null"),
    pytest.param("echo x > NUL", id="redirect-to-nul"),
    pytest.param("ls 2>&1", id="stderr-to-stdout"),
]
NEAR_MISSES = [
    pytest.param('echo "a > b" > {e}/x.txt', id="a-quoted-redirect-sign-then-a-real-one"),
    pytest.param("cat <<EOF > {e}/x.txt\nline\nEOF", id="a-heredoc-with-a-real-redirect"),
    pytest.param('echo "see {e}/y.txt" > {e}/x.txt', id="a-path-in-a-message-then-a-real-one"),
    pytest.param("echo x 2>/dev/null > {e}/x.txt", id="dev-null-then-a-real-one"),
    pytest.param("echo x > NUL; echo y > {e}/x.txt", id="nul-then-a-real-one"),
    pytest.param("echo x 2>&1 > {e}/x.txt", id="2-and-1-then-a-real-one"),
]


@pytest.mark.parametrize("command", PASSING_SHAPES)
@pytest.mark.parametrize("session", [OTHER, LEAD], ids=["session", "lead"])
def test_a_shape_that_names_no_write_target_passes_the_real_hook(proj, session, command):
    """Checks: R274a 8.1 (W75), a quoted `>`, a heredoc body, a path in a message, `>/dev/null`, `NUL` and `2>&1` name no write position: no outside refusal for a session and for a lead."""
    got = shell_decision(proj, session, command.format(e=(proj.base / "sibling").as_posix()))
    assert (got.kind, got.reason_id) == ("allow", None)


@pytest.mark.parametrize("command", NEAR_MISSES)
@pytest.mark.parametrize("session, gate", [(OTHER, "outside.shell"), (LEAD, "lead.shell")], ids=["session", "lead"])
def test_a_near_miss_of_each_shape_is_refused_by_the_real_hook(proj, session, gate, command):
    """Catches: R274a 8.1 (W75), a command that holds one of the six pass shapes and also a real write position outside the root, which passes because of the shape."""
    got = shell_decision(proj, session, command.format(e=(proj.base / "sibling").as_posix()))
    assert (got.kind, got.reason_id, got.gate) == ("deny", "write-outside-root", gate)


def test_a_lead_refusal_at_the_real_hook_carries_the_owner_note(proj):
    """Catches: R274e (5), a lead's refusal that never says who owns the file: the lead gates pass the owner notes to the core, so the text carries the owner table's sentence."""
    got = write_decision(proj, LEAD, proj.root / "src" / "x.py")
    assert (got.kind, got.reason_id, got.gate, "Owner table: " in got.text) == ("deny", "lead-no-edit", "lead.edit", True)

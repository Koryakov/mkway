"""Card MW-017, part 2, rows E5 to E8: what a registered lead may not do. `lead-no-edit` (edit tools and shell) and
`lead-no-take` are form gates (MW-012): watch mode on a first install, the owner's `mkway gate on lead` makes them
block. The gates key on the hook's session id, tool names and paths, never on words. Synthetic roots only."""
import json

import pytest

from _engine import cli, gate_call
from _mw017 import lead_root, new_card, profile_of, register_lead, row_of, state
import dispatch
import gate_lead
import gate_subtask
import gatemode
import leads


def _edit(root, session, path, tool="Write", key="file_path"):
    return gate_call(gate_lead.edit, root, tool=tool, tool_input={key: path, "content": "x"}, session=session)


def _shell(root, session, command):
    return gate_call(gate_lead.shell, root, tool="Bash", tool_input={"command": command}, session=session)


def _order_path(root, card):
    return row_of(root, card)["folder"].strip("`") + "/ORDER.md"


@pytest.fixture
def world(tmp_path):
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    register_lead(root, "lead-b")
    mine = new_card(root, "lead-a", "Mine")
    theirs = new_card(root, "lead-b", "Theirs")
    return root, mine, theirs


def test_a_lead_may_edit_the_order_of_its_cards_and_the_asks_folder(world):
    """E5: the paths a lead may write: `<card folder>/ORDER.md` of a card it ordered, and the asks folder. Catches: a
    lead locked out of its own order file, or out of the asks."""
    root, mine, _theirs = world
    assert _edit(root, "lead-a", _order_path(root, mine)).kind == "allow"
    assert _edit(root, "lead-a", "mkway/asks/q_ask.md").kind == "allow"
    assert _edit(root, "lead-a", "mkway/asks/q_sources.md", tool="Edit").kind == "allow"


def test_a_lead_edit_of_any_other_path_is_lead_no_edit(world, tmp_path):
    """E5, E6: any other path is refused `lead-no-edit`: code, the card file, the order of a card another lead ordered,
    the register; the text names the allowed paths and the owner's `mkway lead remove`. A path outside the repository
    is not this gate's. Edit, Write, MultiEdit and NotebookEdit alike."""
    root, mine, theirs = world
    card_file = row_of(root, mine)["folder"].strip("`") + "/CARD.md"
    for path in ("src/app.py", card_file, _order_path(root, theirs), "mkway/cards/REGISTER.md",
                 "mkway/asks/sub/deep.md.bak/../../../x.py"):
        verdict = _edit(root, "lead-a", path)
        assert verdict.kind == "refuse" and verdict.reason_id == "lead-no-edit", path
    assert "ORDER.md" in verdict.message and "mkway lead remove" in verdict.message
    for tool, key in (("MultiEdit", "file_path"), ("NotebookEdit", "notebook_path")):
        verdict = _edit(root, "lead-a", "src/app.py", tool=tool, key=key)
        assert verdict.kind == "refuse" and verdict.reason_id == "lead-no-edit", tool
    assert _edit(root, "lead-a", str(tmp_path / "elsewhere" / "scratch.txt")).kind == "allow"


def test_a_session_that_is_no_lead_is_not_judged(world):
    """E6: the gate reads the registered leads by session id: a builder, and a lead that was removed, edit as before."""
    root, mine, _theirs = world
    assert _edit(root, "builder-1", "src/app.py").kind == "allow"
    assert _shell(root, "builder-1", "echo x > src/app.py").kind == "allow"
    assert cli(root, "lead", "remove", "lead-a")[0] == 0
    assert _edit(root, "lead-a", "src/app.py").kind == "allow"


def test_the_subtask_gate_lets_a_lead_write_its_order_file(world):
    """E5: a lead holds no card, so the subtask gate would refuse its order file `no-open-card`; it lets that path
    through for a registered lead and keeps refusing the same path for a builder that holds no card."""
    root, mine, _theirs = world
    path = _order_path(root, mine)
    assert gate_call(gate_subtask.check, root, tool="Write", tool_input={"file_path": path}, session="lead-a").kind \
        == "allow"
    verdict = gate_call(gate_subtask.check, root, tool="Write", tool_input={"file_path": path}, session="builder-1")
    assert verdict.kind == "refuse" and verdict.reason_id == "no-open-card"


def test_a_lead_shell_write_is_lead_no_edit(world):
    """E7: a shell command whose write targets are other paths is refused `lead-no-edit`: a redirect, `cp`, `rm`, and a
    program that may write anywhere; its own order file and the asks folder pass; reads and the engine's commands pass."""
    root, mine, _theirs = world
    order = _order_path(root, mine)
    for command in ("echo x > src/app.py", "cp a.txt src/b.txt", "rm src/app.py", "tee src/c.py",
                    "python -c \"import os; os.system('x')\"", "echo x >> mkway/cards/REGISTER.md"):
        verdict = _shell(root, "lead-a", command)
        assert verdict.kind == "refuse" and verdict.reason_id == "lead-no-edit", command
        assert "mkway lead remove" in verdict.message
    for command in (f"echo x > {order}", "echo x > mkway/asks/q_ask.md", "git status", "cat src/app.py",
                    "python mkway/engine/mkway.py card new Another", "python mkway/engine/mkway.py asks",
                    "python mkway/engine/mkway.py ledger add --card CARD-001 --topic t --quote q --source s",
                    "echo x > /dev/null"):
        assert _shell(root, "lead-a", command).kind == "allow", command


def test_a_lead_card_take_is_lead_no_take(world):
    """E7: `card take` by a registered lead, in any spelling the engine call reader knows, is refused `lead-no-take`;
    the text names `mkway card take` as the builder's command and the owner's `mkway lead remove`. A builder's take
    is not judged here."""
    root, mine, _theirs = world
    for command in (f"python mkway/engine/mkway.py card take {mine}", f"python mkway.py card take {mine}",
                    f"bash -c 'python mkway.py card take {mine}'"):
        verdict = _shell(root, "lead-a", command)
        assert verdict.kind == "refuse" and verdict.reason_id == "lead-no-take", command
    assert "mkway card take" in verdict.message and "mkway lead remove" in verdict.message
    assert _shell(root, "builder-1", f"python mkway/engine/mkway.py card take {mine}").kind == "allow"


def _entries():
    return [e for e in dispatch.load_manifest(dispatch.ENGINE_DIR) if e.get("gate") == "lead"]


def test_the_manifest_wires_the_lead_gate_as_a_form_gate_first_in_its_groups():
    """E8: three entries on the gate `lead`, class form: `lead.edit` and `lead.shell` before every other entry of
    their groups (a lead's refusal names the lead rule, not `no-open-card`), `lead.remind` in the prompt group; the
    reasons are declared; the gate class is form."""
    manifest = dispatch.load_manifest(dispatch.ENGINE_DIR)
    by = {e["name"]: e for e in _entries()}
    assert set(by) == {"lead.edit", "lead.shell", "lead.remind"}
    assert all(e["class"] == "form" and e["default_on"] is True and e["status"] == "on" for e in by.values())
    assert by["lead.edit"]["function"] == "gate_lead:edit" and by["lead.edit"]["group"] == "edit"
    assert by["lead.edit"]["matcher"] == "Edit|Write|MultiEdit|NotebookEdit" and by["lead.edit"]["onFailure"] == "block"
    assert by["lead.edit"]["reason_ids"] == ["lead-no-edit"]
    assert by["lead.shell"]["function"] == "gate_lead:shell" and by["lead.shell"]["group"] == "shell"
    assert by["lead.shell"]["matcher"] == "Bash|PowerShell" and by["lead.shell"]["onFailure"] == "block"
    assert by["lead.shell"]["reason_ids"] == ["lead-no-edit", "lead-no-take"]
    assert by["lead.remind"]["function"] == "gate_lead:remind" and by["lead.remind"]["event"] == "UserPromptSubmit"
    assert by["lead.remind"]["reason_ids"] == ["lead-notices-unacked"] and by["lead.remind"]["onFailure"] == "none"
    for group, name in (("edit", "lead.edit"), ("shell", "lead.shell")):
        first = [e["name"] for e in manifest if e["group"] == group and e.get("function")][0]
        assert first == name, group
    assert gatemode.gate_class(manifest, "lead") == gatemode.FORM


def _run(root, tool_input, manifest, group="edit", tool="Write", session="lead-a"):
    payload = {"session_id": session, "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input,
               "cwd": str(root)}
    return dispatch.run("PreToolUse", group, json.dumps(payload),
                        env={"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"}, manifest=manifest)


def test_in_watch_mode_the_refusal_is_logged_and_the_call_goes_ahead(world):
    """E8: with the watch marker the lead gate's refusal is a `would-refuse` row (same reason id and text) and the call
    is allowed; without the marker it is denied; the owner's `mkway gate on lead` removes the marker."""
    root, _mine, _theirs = world
    manifest = [e for e in _entries() if e["name"] in ("lead.edit", "lead.shell")]
    denied = _run(root, {"file_path": "src/app.py", "content": "x"}, manifest)
    assert denied.stdout and json.loads(denied.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "lead-no-edit" in denied.stdout
    gatemode.write_marker(state(root), "lead", "installed")
    allowed = _run(root, {"file_path": "src/app.py", "content": "x"}, manifest)
    assert allowed.exit_code == 0 and not allowed.stdout
    rows = [json.loads(x) for x in (state(root) / "refusals.jsonl").read_text(encoding="utf-8").splitlines()]
    would = [r for r in rows if r.get("kind") == "would-refuse"]
    assert would and would[-1]["reason_id"] == "lead-no-edit" and would[-1]["session"] == "lead-a"
    shell = _run(root, {"command": "python mkway/engine/mkway.py card take CARD-001"}, manifest, "shell", "Bash")
    assert not shell.stdout
    rows = [json.loads(x) for x in (state(root) / "refusals.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["reason_id"] == "lead-no-take" and rows[-1]["kind"] == "would-refuse"
    assert cli(root, "gate", "on", "lead")[0] == 0
    assert not gatemode.is_watching(state(root), "lead")


def test_a_first_install_starts_the_lead_gate_in_watch(tmp_path):
    """E8: the install's watch rule (MW-012, rule 5) covers the new gate: the form gates that are on start in watch."""
    import install
    manifest = dispatch.load_manifest(dispatch.ENGINE_DIR)
    profile = profile_of(lead_root(tmp_path))
    watched = sorted({e.get("gate", e["name"]) for e in manifest if install._loadable_on(profile, e)
                      and gatemode.gate_class(manifest, e.get("gate", e["name"])) == gatemode.FORM})
    assert "lead" in watched

"""The start block names every gate that is off, not only the gates that are on (card MW-007, part 4). Synthetic
task roots only."""
import json

from _engine import entry, task_root
import dispatch
import startline

ENV = {"CLAUDECODE": "1"}


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _set_gates(root, gates):
    profile = _profile(root)
    profile["gates"] = gates
    (root / "mkway" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    return profile


def _block(root, manifest, profile=None, errors=None):
    return startline.render(root, root / "mkway" / "profile.json", profile if profile is not None else _profile(root),
                            errors or [], manifest, ENV, session="s1")


def _line(block, prefix):
    (line,) = [x for x in block.splitlines() if x.startswith(prefix)]
    return line


def _names(line):
    return [n.strip() for n in line.split(":", 1)[1].split(";")[0].split(",") if n.strip() and n.strip() != "none"]


def test_the_start_block_names_every_gate_the_profile_turns_off(tmp_path):
    """E16 (part 4): with the real manifest, a block line `gates off:` names each loaded gate entry that does not
    run, in manifest order, and `none` when all run; a profile switch turns both entries of a gate off; every loaded
    entry is in exactly one of the two lists. Catches: a gate that was switched off and that nothing on the start
    block says, which is how a rule stops holding unseen."""
    manifest = dispatch.load_manifest(dispatch.ENGINE_DIR)
    loaded = [e["name"] for e in manifest if e.get("function") and e.get("reason_ids")]
    root = task_root(tmp_path)
    block = _block(root, manifest)
    assert _line(block, "gates off:") == "gates off: none"
    assert _names(_line(block, "gates on:")) == loaded
    profile = _set_gates(root, {"lock": {"on": False}, "owner_ask": {"on": False}})
    block = _block(root, manifest, profile)
    off = _names(_line(block, "gates off:"))
    assert off == ["lock.edit", "owner_ask.edit", "lock.shell", "owner_ask.notify", "owner_ask.remind",
                   "owner_ask.stop"]  # MW-014 (E7, E12)
    on = _names(_line(block, "gates on:"))
    assert not set(on) & set(off) and sorted(on + off) == sorted(loaded)
    assert block.splitlines().index(_line(block, "gates off:")) == block.splitlines().index(
        _line(block, "gates on:")) + 1


def test_a_gate_without_code_is_not_named_as_off(tmp_path):
    """E17 (part 4): an entry with no function (planned, off-today) is no gate that runs or is off; it stays in
    the count «manifest entries without code yet», and an entry with no reason ids stays in «not loaded».
    Catches: a block that lists thirty names that no switch can change."""
    manifest = [entry("a", "m:f"), entry("planned", None, reason_ids=[]), entry("n1", "m:f", reason_ids=None)]
    root = task_root(tmp_path)
    block = _block(root, manifest)
    assert _line(block, "gates off:") == "gates off: none"
    assert "not loaded: n1 (no reason_ids)" in _line(block, "gates on:")
    assert "1 manifest entries without code yet" in _line(block, "gates on:")


def test_a_default_off_gate_and_a_nested_mode_are_named_as_off(tmp_path):
    """E18 (part 4): a gate whose manifest default is off, a gate the profile switches off and a nested mode the
    profile switches off are each named; a gate the profile turns on stays out of the list.
    Catches: a list that knows only the profile's own `on: false`."""
    manifest = [entry("a", "m:f"), entry("b", "m:f", default_on=False), entry("c", "m:f"),
                entry("d.mode", "m:f"), entry("e", "m:f", default_on=False)]
    root = task_root(tmp_path)
    profile = _set_gates(root, {"c": {"on": False}, "d": {"mode": {"on": False}}, "e": {"on": True}})
    block = _block(root, manifest, profile)
    assert _names(_line(block, "gates off:")) == ["b", "c", "d.mode"]
    assert _names(_line(block, "gates on:")) == ["a", "e"]


def test_an_invalid_profile_names_every_loaded_gate_as_off(tmp_path):
    """E19 (part 4): while the profile is invalid no gate runs, so the block names each loaded gate as off (and
    `gates on` is none). Catches: a block that says `gates off: none` while every gate is silent."""
    manifest = [entry("a", "m:f"), entry("b", "m:f")]
    root = task_root(tmp_path)
    block = _block(root, manifest, errors=["state: missing"])
    assert _names(_line(block, "gates off:")) == ["a", "b"]
    assert _line(block, "gates on:").startswith("gates on: none")


def test_the_dispatcher_prints_the_off_line_at_session_start(tmp_path):
    """E16 (part 4): the SessionStart hook's context carries the same `gates off:` line. Catches: a block that is
    right in `startline.render` but not what the session is shown."""
    root = task_root(tmp_path)
    _set_gates(root, {"owner_ask": {"on": False}})
    payload = {"session_id": "s1", "hook_event_name": "SessionStart"}
    res = dispatch.run("SessionStart", "start", json.dumps(payload),
                       env={"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"})
    context = json.loads(res.stdout)["hookSpecificOutput"]["additionalContext"]
    assert ("gates off: owner_ask.edit, owner_ask.notify, owner_ask.remind, owner_ask.stop"
            in context)  # MW-014 (E7, E12)

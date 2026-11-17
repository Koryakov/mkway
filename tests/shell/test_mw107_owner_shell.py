"""Card MW-107 (concept line 1, kind K6; rulings R270a, R270c): the shells of the three gates read the owner table: the
subtask gate and the lead gate's shell refuse a write outside the root for every session unless the outside-writable list
names it, the lead's writable set and the commit scope read the same rows, and the dedup blocks replay on a real small git
repo. Fake home and temp folders only (USERPROFILE, HOME, TEMP and TMP point at tmp_path); the real ones are never read.
Synthetic names and sessions only."""
import json
from collections import namedtuple

import pytest

from _engine import cli, gate_call, task_root
import _mw017 as lead_helpers
import _mw080 as w
import _mw102 as v
import gate_lead
import gate_outside
import gate_subtask
import leads
import profiles
import records
import register
import re

World = namedtuple("World", "root home temp elsewhere")
WAY_OUT = "a file the task needs elsewhere is a folder the owner adds to paths.outside_writable"  # R274 text, after the root
CLI = "python mkway/engine/mkway.py"


def case(id_, *values):
    return pytest.param(*values, id=id_)


def profile_of(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def card_file(root, card_id):
    (folder,) = [p for p in (root / "mkway" / "cards").iterdir() if p.name.startswith(card_id + "-")]
    return folder / "CARD.md"


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A task root where session `s1` holds the open card CARD-001 (Paths `src/a.py`), and fake home, temp and elsewhere."""
    home, temp, elsewhere = tmp_path / "home", tmp_path / "temp", tmp_path / "elsewhere"
    for folder in (home, temp, elsewhere):
        folder.mkdir()
    for name in ("USERPROFILE", "HOME"):
        monkeypatch.setenv(name, str(home))
    for name in ("TEMP", "TMP"):
        monkeypatch.setenv(name, str(temp))
    root = task_root(tmp_path, name="task")
    assert cli(root, "card", "new", "First", session=True)[0] == 0
    path = card_file(root, "CARD-001")
    path.write_text(re.sub(r"^\| \*\*Paths\*\* \|.*\|$", "| **Paths** | `src/a.py` |", path.read_text(encoding="utf-8"),
                           flags=re.M), encoding="utf-8")
    records.append(root / "mkway" / "state", "s1", "take", "CARD-001")
    assert cli(root, "card", "open", "CARD-001")[0] == 0
    return World(root, home, temp, elsewhere)


def verdict_of(verdict):
    return (verdict.reason_id, verdict.message) if verdict.kind == "refuse" else ("allow", "")


def edit(world, path, session="s1", profile=None):
    """R274e: a session's edit outside the root is judged by the outside gate (`outside.edit`), not by the subtask gate."""
    return verdict_of(gate_call(gate_outside.edit, world.root, tool="Write", tool_input={"file_path": str(path), "content": "x"},
                                session=session, profile=profile))


def shell(world, command, session="s1"):
    """R274e: a session's shell write outside the root is judged by the outside gate (`outside.shell`)."""
    return verdict_of(gate_call(gate_outside.shell, world.root, tool="Bash", tool_input={"command": command}, session=session))


@pytest.mark.parametrize("where", [
    case("another-checkout", ("elsewhere", "other-checkout", "conftest.py")),
    case("the-home-settings-file", ("home", ".claude", "settings.json")),
    case("another-temp-folder", ("temp", "other", "x.txt")),
])
def test_a_session_edit_outside_the_root_is_refused_by_the_subtask_gate(world, where):
    """Catches: a session with an open card that writes a file outside its root through an edit tool and is let through."""
    base = {"elsewhere": world.elsewhere, "home": world.home, "temp": world.temp}[where[0]]
    reason, message = edit(world, base.joinpath(*where[1:]))
    root = world.root.resolve().as_posix()
    assert (reason, WAY_OUT in message, f"write the file inside {root};" in message) == ("write-outside-root", True, True)


@pytest.mark.parametrize("where", [
    case("memory", ("home", ".claude", "projects", "p", "memory", "m.md")),
    case("plans", ("home", ".claude", "plans", "a.md")),
    case("harness-temp", ("temp", "claude", "s", "x.txt")),
])
def test_the_harness_folders_stay_writable_for_every_session(world, where):
    """Checks: the memory, plans and temp folders of the harness are on the outside-writable list for a session that is no lead."""
    base = {"home": world.home, "temp": world.temp}[where[0]]
    assert edit(world, base.joinpath(*where[1:]))[0] == "allow"


def test_a_folder_the_profile_adds_opens_for_every_session(world):
    """Catches: a profile addition to the outside-writable list that opens for leads only, or one that re-opens the settings files."""
    profile = profile_of(world.root)
    profile["paths"] = {**profile.get("paths", {}),
                        "outside_writable": [world.elsewhere.as_posix() + "/**", "<home>/.claude/settings*.json"]}
    got = (edit(world, world.elsewhere / "n" / "a.md", profile=profile)[0], edit(world, world.elsewhere / "n" / "a.md")[0],
           edit(world, world.home / ".claude" / "settings.json", profile=profile)[0])
    assert got == ("allow", "write-outside-root", "write-outside-root")


@pytest.mark.parametrize("command, expected", [
    case("redirect-outside", "echo x > {elsewhere}/a.txt", "write-outside-root"),
    case("copy-outside", "cp a.txt {elsewhere}/b.txt", "write-outside-root"),
    case("tee-outside", "echo x | tee {elsewhere}/c.txt", "write-outside-root"),
    case("redirect-inside", "echo x > src/a.py", "allow"),
    case("dev-null", "echo x > /dev/null", "allow"),
    case("a-read-outside", "cat {elsewhere}/a.txt", "allow"),
    case("harness-temp", "echo x > {temp}/claude/s/x.txt", "allow"),
])
def test_a_session_shell_write_outside_the_root_is_refused(world, command, expected):
    """Catches: a shell redirect or copy outside the root that a session with a card makes unseen; and a read, a write inside or a harness folder blocked."""
    text = command.format(elsewhere=world.elsewhere.as_posix(), temp=world.temp.as_posix())
    assert shell(world, text)[0] == expected


def test_a_command_that_names_a_delete_program_is_left_to_the_delete_gate(world):
    """Checks: `rm` of a path outside the root is no second reason here: the delete gate refuses it with its own id."""
    assert shell(world, f"rm {world.elsewhere.as_posix()}/outside.txt")[0] == "allow"


@pytest.fixture
def leaders(tmp_path):
    """Two registered leads, each with a card it wrote (CARD-001 mine, CARD-002 theirs), both proposed."""
    root = lead_helpers.lead_root(tmp_path)
    for session in ("lead-a", "lead-b"):
        lead_helpers.register_lead(root, session)
    assert lead_helpers.new_card(root, "lead-a", "Mine") == "CARD-001"
    assert lead_helpers.new_card(root, "lead-b", "Theirs") == "CARD-002"
    return root


def folder_of(root, card_id):
    return card_file(root, card_id).parent.relative_to(root).as_posix()


@pytest.mark.parametrize("card, name, expected", [
    case("own-order", "CARD-001", "ORDER.md", True),
    case("own-fix-round-order", "CARD-001", "ORDER_fix1.md", True),
    case("own-card-file-while-proposed", "CARD-001", "CARD.md", True),
    case("another-leads-fix-round-order", "CARD-002", "ORDER_fix1.md", False),
    case("a-file-that-only-looks-like-an-order", "CARD-001", "ORDER.txt", False),
    case("the-case-map-of-the-card", "CARD-001", "case_map.md", False),
])
def test_a_lead_writes_every_order_file_of_a_card_it_ordered(leaders, card, name, expected):
    """Catches: a lead refused the fix-round order file of its own card, or let write another lead's order or a file that is no order."""
    rel = f"{folder_of(leaders, card)}/{name}"
    verdict = gate_call(gate_lead.edit, leaders, tool="Write", tool_input={"file_path": rel, "content": "x"}, session="lead-a")
    assert (verdict.kind != "refuse", leads.writable(leaders, profile_of(leaders), "lead-a", rel)) == (expected, expected)


@pytest.mark.parametrize("write", [
    case("edit-tool", lambda world, target: edit(world, target)),
    case("shell", lambda world, target: shell(world, f"printf xxxxxxxxxxxx > {target}")),
])
def test_replay_a_12_byte_conftest_written_into_another_checkout_is_refused(world, write):
    """Catches: the real case, a builder wrote a 12-byte conftest.py by a wrong absolute path into another checkout and nothing refused it."""
    target = (world.elsewhere / "another-checkout" / "conftest.py").as_posix()
    assert write(world, target)[0] == "write-outside-root"


def hold_the_folder(root):
    """The card's Paths cover its whole folder, as a builder's card does (`cards/<id>-*/**`)."""
    def mutate(table):
        row = register.find(table, v.CARD)
        row["paths"] = row["folder"]
        return table
    register.write(root, profile_of(root), mutate)


def commit_of(root, rel, text="x", session=v.LEAD, message="CARD-001 the file"):
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text, encoding="utf-8")
    w.git(root, "add", "-f", "--", rel)
    return v.decide(root, f"git commit -m '{message}' -- {rel}", session=session)


def registered(root, session=v.LEAD):
    assert leads.register_lead(profiles.shared_state_dir(root, profile_of(root)), session)


def test_replay_the_orderer_commits_an_order_file_its_card_paths_cover(tmp_path):
    """Catches: the real case, the orderer refused `ORDER_fix1.md` of its own card because the card's Paths cover the folder."""
    root = v.verdict_root(tmp_path)
    hold_the_folder(root)
    assert commit_of(root, folder_of(root, v.CARD) + "/ORDER_fix1.md") == ("allow", "")


def test_replay_the_lead_commits_an_ask_file(tmp_path):
    """Catches: the real case, a registered lead that holds no card refused the ask file it wrote."""
    root = v.verdict_root(tmp_path)
    registered(root)
    assert commit_of(root, "mkway/asks/q_ask.md") == ("allow", "")


def test_replay_the_lead_commits_a_quote_file(tmp_path):
    """Catches: the real case, a registered lead that holds no card refused the quote file of an owner answer."""
    root = v.verdict_root(tmp_path)
    registered(root)
    assert commit_of(root, "mkway/asks/D-12_quote.md") == ("allow", "")


def test_replay_the_orderer_commits_the_verdict_file(tmp_path):
    """Checks: the verdict file of a closed card is the orderer's (a regression pin of MW-102, green before this card)."""
    root = v.verdict_root(tmp_path)
    v.add(root, v.N1, v.N2, v.N3, v.B1)
    v.close_card(root)
    v.stage(root)
    assert v.decide(root) == ("allow", "")


def test_a_builder_still_may_not_commit_the_ask_file_of_a_lead(tmp_path):
    """Catches: an ask file that any session may commit; the text must name the orderer and the way out."""
    root = v.verdict_root(tmp_path)
    reason, text = commit_of(root, "mkway/asks/q_ask.md", session="builder-1")
    assert (reason, "`mkway/asks/q_ask.md` is the orderer's (asks)" in text, "Owner table:" in text) == ("file-not-in-card", True, True)


def subtask_edit(world, path, session="s1", profile=None):
    return verdict_of(gate_call(gate_subtask.check, world.root, tool="Write", tool_input={"file_path": str(path), "content": "x"},
                                session=session, profile=profile))


def test_the_way_out_of_a_no_owner_refusal_works_through_the_subtask_gate(world):
    """Catches: R274e (8), a refusal of a path that has no owner row whose named way out is only a sentence: refused naming `paths.exempt`, then the profile names the kind, then the same write is allowed."""
    target = world.root / "docs" / "x.md"
    refused = subtask_edit(world, target)
    profile = profile_of(world.root)
    profile["paths"] = {**profile.get("paths", {}), "exempt": ["docs/**"]}
    allowed = subtask_edit(world, target, profile=profile)
    assert (refused[0], "has no owner row" in refused[1], "`paths.exempt`" in refused[1], allowed[0]) == (
        "file-not-in-card", True, True, "allow")

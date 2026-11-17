"""Card MW-066: the shell of the session family's gates reads its facts from real files (the sealed register, the card
file, the records, the leads file, the shared inbox, the nonce store) and writes what the verdict says. The decisions are
proven by `tests/core/test_session_decide.py`; here each test id is one case that proves one fact is read right or one wire
is connected, on a synthetic task root built by a fixture of this file. One id, one case; no body loops over cases. Worlds
that tests only read are built once per module; a test that changes state builds its own. Every test runs under 20 s (the
cap of the ruling). Synthetic roots and session ids only; nothing outside the test's temp root."""
import datetime
import json
import re
import sys
import time

import pytest

from _engine import cli, gate_call, jsonl, make_profile, task_root
import core_session
import dispatch
import gate_lead
import gate_lock
import gate_message
import gate_records
import gate_subtask
import gatemode
import install
import leads
import messages
import records
import register
import sessions

CAP_SECONDS = 20.0


def now():
    """The clock of a test's rows: read when a fixture or test runs, never at import (MW-141, MW141-D1)."""
    return datetime.datetime.now(datetime.timezone.utc)


@pytest.fixture(autouse=True)
def _a_shell_test_takes_under_20_seconds():
    started = time.perf_counter()
    yield
    took = time.perf_counter() - started
    assert took < CAP_SECONDS, f"a shell test must run under {CAP_SECONDS:g} s; this one took {took:.1f} s"


def case(id_, *values):
    return pytest.param(*values, id=id_)


# ---- the fixtures: synthetic roots and a session's command as the hooks run it -----------------------------------------

def state(root):
    return root / "mkway" / "state"


def profile_of(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def lead_root(tmp_path, **over):
    over.setdefault("cards", {"approver": "orderer"})
    return task_root(tmp_path, **over)


def session_run(root, session, *args):
    """A session's mkway command as the hooks run it: the lock gate first (it leaves the one-use permit that names the
    session), then the CLI in a session's shell, then the `post` record step. Returns (code, out, err)."""
    command = "python mkway/engine/mkway.py " + " ".join(args)
    verdict = gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": command}, session=session)
    assert verdict.kind != "refuse", f"{verdict.reason_id}: {verdict.message}"
    code, out, err = cli(root, *args, session=True)
    if code == 0:
        gate_call(gate_records.record, root, tool="Bash", tool_response={"stdout": out}, session=session, event="PostToolUse")
    return code, out, err


def new_card(root, session, title):
    code, out, err = session_run(root, session, "card", "new", title)
    assert code == 0, err
    return re.search(r"(CARD-\d{3})", out).group(1)


def register_lead(root, session):
    code, _out, err = session_run(root, session, "lead", "register")
    assert code == 0, err


def card_file(root, card_id):
    (folder,) = [p for p in (root / "mkway" / "cards").iterdir() if p.name.startswith(card_id + "-")]
    return folder / "CARD.md"


def set_paths(root, card_id, value):
    path = card_file(root, card_id)
    text = re.sub(r"^\| \*\*Paths\*\* \|.*\|$", f"| **Paths** | {value} |", path.read_text(encoding="utf-8"), flags=re.M)
    path.write_text(text, encoding="utf-8")


def take(root, session="s1"):
    records.append(state(root), session, "take", "CARD-001")


def card_root(tmp_path, name):
    """A task root with one card `CARD-001` (Paths `src/a.py` and `lib/`) and exempt path `notes/**`."""
    root = task_root(tmp_path, name=name, paths={"exempt": ["notes/**"]})
    assert cli(root, "card", "new", "First", session=True)[0] == 0
    set_paths(root, "CARD-001", "`src/a.py`, `lib/`")
    return root


# ---- the subtask gate reads the register, the records and the card file ----------------------------------------------------

@pytest.fixture(scope="module")
def subtask_roots(tmp_path_factory):
    """Roots in the states the subtask facts are read from; each is built once and only read by the tests."""
    base = tmp_path_factory.mktemp("subtask")
    roots = {}
    roots["fresh"] = card_root(base, "fresh")  # the card is written, nobody holds it
    roots["proposed"] = card_root(base, "proposed")  # held; the card file says open, the register says proposed
    take(roots["proposed"])
    file = card_file(roots["proposed"], "CARD-001")
    file.write_text(file.read_text(encoding="utf-8").replace("| **Status** | proposed |", "| **Status** | open |"),
                    encoding="utf-8")
    for name in ("open", "reordered", "widened", "reopened", "waiting", "unreadable", "emptied"):
        roots[name] = card_root(base, name)
        take(roots[name])
    set_paths(roots["emptied"], "CARD-001", "")
    for name in ("open", "reordered", "widened", "reopened", "waiting", "unreadable", "emptied"):
        assert cli(roots[name], "card", "open", "CARD-001")[0] == 0
    set_paths(roots["reordered"], "CARD-001", "`./lib/` ,  `src/a.py`")
    set_paths(roots["widened"], "CARD-001", "`src/a.py`, `lib/`, `src/b.py`")
    set_paths(roots["reopened"], "CARD-001", "`src/b.py`")
    assert cli(roots["reopened"], "card", "open", "CARD-001")[0] == 0  # an open card's re-open records nothing
    register.set_status(roots["waiting"], profile_of(roots["waiting"]), "CARD-001", "waiting")
    card_file(roots["unreadable"], "CARD-001").unlink()
    roots["tampered"] = card_root(base, "tampered")
    take(roots["tampered"])
    reg = roots["tampered"] / "mkway" / "cards" / "REGISTER.md"
    reg.write_bytes(reg.read_bytes().replace(b"proposed", b"open"))
    return roots


def edit(root, path, session="s1"):
    verdict = gate_call(gate_subtask.check, root, tool="Edit", tool_input={"file_path": path}, session=session)
    return verdict.reason_id if verdict.kind == "refuse" else "allow"


@pytest.mark.parametrize("name, path, session, expected", [
    case("no-card-held-denies", "fresh", "src/a.py", "s1", "no-open-card"),
    case("another-session-holds-nothing-denies", "open", "src/a.py", "s2", "no-open-card"),
    case("the-card-file-with-no-card-held-allows", "fresh", "mkway/cards/CARD-001-first/CARD.md", "s1", "allow"),
    case("an-exempt-path-with-no-card-held-allows", "fresh", "notes/today.md", "s1", "allow"),
    case("register-proposed-denies-though-the-card-file-says-open", "proposed", "src/a.py", "s1", "card-not-open"),
    case("register-waiting-denies", "waiting", "src/a.py", "s1", "card-not-open"),
    case("register-open-allows-a-recorded-file", "open", "src/a.py", "s1", "allow"),
    case("register-open-allows-a-file-in-a-recorded-folder", "open", "lib/deep/x.py", "s1", "allow"),
    case("register-open-denies-a-file-outside", "open", "src/b.py", "s1", "file-not-in-card"),
    case("register-open-denies-the-same-tail-elsewhere", "open", "other/src/a.py", "s1", "file-not-in-card"),
    case("an-empty-recorded-paths-allows-any-file", "emptied", "anything/at/all.py", "s1", "allow"),
    case("paths-reordered-with-spaces-and-dot-slash-allows", "reordered", "src/a.py", "s1", "allow"),
    case("paths-widened-denies", "widened", "src/a.py", "s1", "card-paths-changed"),
    case("paths-widened-leaves-the-card-file-editable", "widened", "mkway/cards/CARD-001-first/CARD.md", "s1", "allow"),
    case("paths-rewritten-and-reopened-still-denies", "reopened", "src/b.py", "s1", "card-paths-changed"),
    case("a-card-file-that-cannot-be-read-denies", "unreadable", "src/a.py", "s1", "card-paths-changed"),
    case("a-tampered-register-denies-every-edit", "tampered", "src/a.py", "s1", "register-tampered"),
])
def test_the_subtask_facts_are_read_from_the_register_the_records_and_the_card_file(subtask_roots, name, path, session, expected):
    """Catches: a status read from the card file, a held card taken from the wrong session, or an unsealed register trusted."""
    # Paths are compared as normalised sets, a re-open widens nothing, an unreadable card file is not read as unchanged
    assert edit(subtask_roots[name], path, session) == expected


# ---- the lead gate reads the leads file, the register and the shell reader -------------------------------------------------

@pytest.fixture(scope="module")
def lead_worlds(tmp_path_factory):
    """Two leads, each with a card it wrote (`mine`, `theirs`, both proposed); `sealed` is the same with `mine` opened."""
    worlds = {}
    for name in ("proposed", "sealed"):
        root = lead_root(tmp_path_factory.mktemp(name))
        register_lead(root, "lead-a")
        register_lead(root, "lead-b")
        assert new_card(root, "lead-a", "Mine") == "CARD-001" and new_card(root, "lead-b", "Theirs") == "CARD-002"
        worlds[name] = root
    assert cli(worlds["sealed"], "card", "open", "CARD-001")[0] == 0
    return worlds


MINE, THEIRS = "mkway/cards/CARD-001-mine", "mkway/cards/CARD-002-theirs"


def lead_edit(root, session, path, tool="Write", key="file_path"):
    verdict = gate_call(gate_lead.edit, root, tool=tool, tool_input={key: path, "content": "x"}, session=session)
    return verdict.reason_id if verdict.kind == "refuse" else "allow"


def subtask_write(root, session, path):
    verdict = gate_call(gate_subtask.check, root, tool="Write", tool_input={"file_path": path}, session=session)
    return verdict.reason_id if verdict.kind == "refuse" else "allow"


@pytest.mark.parametrize("world, session, path, expected", [
    case("its-order-file-allows", "proposed", "lead-a", f"{MINE}/ORDER.md", "allow"),
    case("its-card-file-while-proposed-allows", "proposed", "lead-a", f"{MINE}/CARD.md", "allow"),
    case("its-card-file-once-opened-denies", "sealed", "lead-a", f"{MINE}/CARD.md", "lead-no-edit"),
    case("its-order-file-once-opened-allows", "sealed", "lead-a", f"{MINE}/ORDER.md", "allow"),
    case("an-asks-file-allows", "proposed", "lead-a", "mkway/asks/q_ask.md", "allow"),
    case("another-leads-order-denies", "proposed", "lead-a", f"{THEIRS}/ORDER.md", "lead-no-edit"),
    case("another-leads-proposed-card-file-denies", "proposed", "lead-a", f"{THEIRS}/CARD.md", "lead-no-edit"),
    case("code-denies", "proposed", "lead-a", "src/app.py", "lead-no-edit"),
    case("the-register-denies", "proposed", "lead-a", "mkway/cards/REGISTER.md", "lead-no-edit"),
    case("a-path-that-climbs-out-of-the-asks-denies", "proposed", "lead-a", "mkway/asks/sub/deep.md.bak/../../../x.py", "lead-no-edit"),
    case("a-builder-is-not-judged", "proposed", "builder-1", f"{MINE}/ORDER.md", "allow"),
])
def test_what_a_lead_may_write_is_read_from_its_register_rows_and_the_card_status(lead_worlds, world, session, path, expected):
    """Catches: a lead locked out of its own files, a card file still writable once opened, or another lead's files writable."""
    assert lead_edit(lead_worlds[world], session, path) == expected


@pytest.mark.parametrize("tool, key", [case("multi-edit", "MultiEdit", "file_path"), case("notebook-edit", "NotebookEdit", "notebook_path")])
def test_the_other_edit_tools_are_read_by_their_own_path_key(lead_worlds, tool, key):
    """Catches: a lead that writes code through a tool or a path key the gate does not read."""
    assert lead_edit(lead_worlds["proposed"], "lead-a", "src/app.py", tool, key) == "lead-no-edit"


@pytest.mark.parametrize("world, session, path, expected", [
    case("a-lead-writes-its-order-with-no-card", "proposed", "lead-a", f"{MINE}/ORDER.md", "allow"),
    case("a-lead-writes-its-card-file-while-proposed", "proposed", "lead-a", f"{MINE}/CARD.md", "allow"),
    case("a-lead-writes-its-order-once-opened", "sealed", "lead-a", f"{MINE}/ORDER.md", "allow"),
    case("a-lead-writes-another-leads-order-and-holds-no-card", "proposed", "lead-a", f"{THEIRS}/ORDER.md", "no-open-card"),
    case("a-builder-writes-an-order-file-and-holds-no-card", "proposed", "builder-1", f"{MINE}/ORDER.md", "no-open-card"),
])
def test_the_subtask_gate_lets_a_lead_write_what_the_lead_rule_allows(lead_worlds, world, session, path, expected):
    """Catches: a lead whose order file is refused no-open-card because it holds no card, or a builder let through the same way."""
    assert subtask_write(lead_worlds[world], session, path) == expected


def test_a_path_outside_the_repository_is_not_the_lead_gates(lead_worlds, tmp_path):
    """Catches: a lead that writes a scratch file outside the repository and outside the harness's own folders (changed by MW-103, R255: it is lead-no-edit now)."""
    assert lead_edit(lead_worlds["proposed"], "lead-a", str(tmp_path / "elsewhere" / "scratch.txt")) == "write-outside-root"  # R274-D2


def test_a_lead_that_was_removed_is_not_judged(tmp_path):
    """Catches: a lead that keeps being judged by the lead rule after the owner's `lead remove`."""
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    assert cli(root, "lead", "remove", "lead-a")[0] == 0
    assert lead_edit(root, "lead-a", "src/app.py") == "allow"


def lead_shell(root, session, command):
    verdict = gate_call(gate_lead.shell, root, tool="Bash", tool_input={"command": command}, session=session)
    return verdict.reason_id if verdict.kind == "refuse" else "allow"


@pytest.mark.parametrize("command, expected", [
    case("a-redirect-into-code-denies", "echo x > src/app.py", "lead-no-edit"),
    case("a-copy-into-code-denies", "cp a.txt src/b.txt", "lead-no-edit"),
    case("a-remove-of-code-denies", "rm src/app.py", "lead-no-edit"),
    case("a-tee-into-code-denies", "tee src/c.py", "lead-no-edit"),
    case("an-append-to-the-register-denies", "echo x >> mkway/cards/REGISTER.md", "lead-no-edit"),
    case("a-program-that-can-write-anywhere-denies", "python -c \"import os; os.system('x')\"", "lead-no-edit"),
    case("a-redirect-into-its-order-allows", f"echo x > {MINE}/ORDER.md", "allow"),
    case("a-redirect-into-an-asks-file-allows", "echo x > mkway/asks/q_ask.md", "allow"),
    case("a-redirect-into-dev-null-allows", "echo x > /dev/null", "allow"),
    case("git-status-allows", "git status", "allow"),
    case("a-read-allows", "cat src/app.py", "allow"),
    case("the-engines-card-new-allows", "python mkway/engine/mkway.py card new Another", "allow"),
    case("the-engines-asks-allows", "python mkway/engine/mkway.py asks", "allow"),
    case("card-take-by-the-engine-path-denies", "python mkway/engine/mkway.py card take CARD-001", "lead-no-take"),
    case("card-take-by-the-short-path-denies", "python mkway.py card take CARD-001", "lead-no-take"),
    case("card-take-inside-bash-c-denies", "bash -c 'python mkway.py card take CARD-001'", "lead-no-take"),
])
def test_the_shell_reader_hands_the_core_the_writes_of_a_command_and_a_card_take(lead_worlds, command, expected):
    """Catches: a lead write outside its files, a card take in any spelling, or a lead blocked from reads and its own files."""
    assert lead_shell(lead_worlds["proposed"], "lead-a", command) == expected


def test_a_builder_takes_a_card_and_the_lead_gate_does_not_judge_it(lead_worlds):
    """Catches: the lead rule applied to a session that is no lead."""
    assert lead_shell(lead_worlds["proposed"], "builder-1", "python mkway/engine/mkway.py card take CARD-001") == "allow"


@pytest.fixture(scope="module")
def notice_roots(tmp_path_factory):
    """`unacked`: lead-a has one unacked notice; `acked`: the same notice acked; `none`: a lead with an empty inbox."""
    roots = {}
    for name in ("unacked", "acked", "none"):
        root = lead_root(tmp_path_factory.mktemp(name))
        register_lead(root, "lead-a")
        roots[name] = root
    row = messages.make_row("engine", "lead-a", "notice", "past its Appetite", None, now())
    messages.append_row(state(roots["unacked"]), row)
    messages.append_row(state(roots["acked"]), row)
    leads.ack(state(roots["acked"]), "lead-a", row["id"])
    roots["row"] = row
    return roots


@pytest.mark.parametrize("name, session, kind", [
    case("a-lead-with-an-unacked-notice-is-warned", "unacked", "lead-a", "warn"),
    case("a-lead-with-the-notice-acked-is-not", "acked", "lead-a", "allow"),
    case("a-lead-with-an-empty-inbox-is-not", "none", "lead-a", "allow"),
    case("a-session-that-is-no-lead-is-not", "unacked", "build-a1", "allow"),
])
def test_the_lead_reminder_reads_the_unacked_notices_of_the_leads_own_inbox(notice_roots, name, session, kind):
    """Catches: a lead never told of an unacked notice, told again after it acked, or a builder told a lead's notices."""
    assert gate_call(gate_lead.remind, notice_roots[name], session=session, event="UserPromptSubmit").kind == kind


def test_the_lead_reminder_names_the_notice_and_its_ack_command(notice_roots):
    """Catches: a reminder that does not carry the notice text and the command that acks it."""
    row = notice_roots["row"]
    verdict = gate_call(gate_lead.remind, notice_roots["unacked"], session="lead-a", event="UserPromptSubmit")
    assert verdict.reason_id == "lead-notices-unacked"
    assert f"{row['id']}: past its Appetite (`mkway ack {row['id']}`)" in verdict.message


# ---- the message gate reads the inbox, the pings and the ages of orders ----------------------------------------------------

@pytest.fixture
def mail(tmp_path):
    """Two leads; `build-a1` and `build-a2` hold cards lead-a ordered; every session is in the shared sessions file. Rows
    (`rows`): `allowed` and `recorded` and `watched` are unpinged orders of lead-a to build-a1; `pinged` has its ping
    recorded; `question` is lead-b's to lead-a; `notice` is the engine's to lead-a; `dead` is a dead-letter row."""
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    register_lead(root, "lead-b")
    cards = {"build-a1": new_card(root, "lead-a", "First"), "build-a2": new_card(root, "lead-a", "Second")}
    for who, card in cards.items():
        assert session_run(root, who, "card", "take", card)[0] == 0
    for sid in ("lead-a", "lead-b", "build-a1", "build-a2", "free-1"):
        sessions.append(state(root), sid, root)
    rows = {}
    for key, (sender, to, kind) in {"allowed": ("lead-a", "build-a1", "order"), "recorded": ("lead-a", "build-a1", "order"),
                                    "watched": ("lead-a", "build-a1", "order"), "pinged": ("lead-a", "build-a1", "order"),
                                    "question": ("lead-b", "lead-a", "question")}.items():
        (root / f"{key}.txt").write_text(f"the {key} body", encoding="utf-8")
        code, out, err = session_run(root, sender, "send", "--to", to, "--kind", kind, "--file", f"{key}.txt")
        assert code == 0, err
        rows[key] = re.search(r"^mkway inbox (\S+)$", out, re.M).group(1)
    messages.record_ping(state(root), rows["pinged"], "lead-a")
    rows["notice"] = leads.append_notice(state(root), "lead-a", "a matter the engine wrote")["id"]
    (root / "dead.txt").write_text("anyone?", encoding="utf-8")
    assert session_run(root, "build-a1", "send", "--to", "zzz-nobody", "--kind", "question", "--file", "dead.txt")[0] != 0
    (dead,) = jsonl(state(root) / "dead-letter.jsonl")
    rows["dead"] = dead["id"]
    return root, rows


def ping(root, session, text, **extra):
    return gate_call(gate_message.check, root, tool="SendMessage", session=session,
                     tool_input=dict({"to": "somebody", "message": text}, **extra))


def pings(root):
    return jsonl(state(root) / "pings.jsonl")


@pytest.mark.parametrize("session, row, expected", [
    case("the-sender-of-an-unpinged-row-allows", "lead-a", "allowed", "allow"),
    case("the-sender-of-a-pinged-row-is-a-duplicate", "lead-a", "pinged", "message-duplicate"),
    case("the-recipient-pinging-its-received-row-passes", "build-a1", "allowed", "allow"),
    case("another-lead-passes", "lead-b", "allowed", "allow"),
    case("a-session-with-no-row-passes", "free-1", "allowed", "allow"),
    case("the-sender-of-another-senders-row-passes", "lead-a", "question", "allow"),
    case("a-row-the-engine-wrote-passes", "lead-a", "notice", "allow"),
    case("a-dead-letter-row-passes", "build-a1", "dead", "allow"),
    case("an-id-that-does-not-exist-passes", "lead-a", "m-20990101000000-ffffff", "allow"),
])
def test_the_send_gate_finds_the_row_in_the_shared_inbox_and_whether_it_was_pinged(mail, session, row, expected):
    """Catches: MW-110: a SendMessage that carries the ping line of a row the session did not write is no longer refused; a second ping of the sender's own row still is."""
    # the sender's own first ping (the docstring's old case) is covered by the row "the-sender-of-an-unpinged-row-allows"
    root, rows = mail
    verdict = ping(root, session, f"mkway inbox {rows.get(row, row)}")
    assert (verdict.reason_id if verdict.kind == "refuse" else "allow") == expected


@pytest.mark.parametrize("session", [case("none", None), case("empty", ""), case("number", 5)])
def test_a_session_the_hook_gives_no_id_for_is_not_judged_and_records_no_ping(mail, session):
    """Catches: MW-110: a ping from a call whose sender cannot be established is refused as before, or recorded."""
    root, rows = mail
    before = pings(root)
    verdict = gate_call(gate_message.check, root, tool="SendMessage", session=session,
                        tool_input={"message": f"mkway inbox {rows['allowed']}"})
    assert verdict.kind == "allow"
    assert pings(root) == before


def test_an_allowed_ping_appends_one_ping_row_with_the_row_id_the_session_and_a_time(mail):
    """Catches: an allowed ping that is not recorded (a second ping would then pass), or a ping row without its session."""
    root, rows = mail
    before = pings(root)
    assert ping(root, "lead-a", f"mkway inbox {rows['recorded']}\n").kind == "allow"
    (row,) = [r for r in pings(root) if r not in before]
    assert (row["id"], row["session"]) == (rows["recorded"], "lead-a")
    assert row["ts"]


def test_a_ping_line_of_another_senders_row_appends_nothing(mail):
    """Catches: MW-110 (decision MW110-D2): the ping line of another session's row is no longer refused, and it must not
    be recorded as that session's ping, which would block the real one."""
    root, rows = mail
    before = pings(root)
    assert ping(root, "lead-b", f"mkway inbox {rows['recorded']}").kind == "allow"
    assert pings(root) == before


def test_the_line_mkway_send_prints_is_the_line_the_gate_reads():
    """Catches: a ping line that `mkway send` prints and the gate then refuses (two definitions that drifted apart)."""
    assert core_session.PING_LINE is messages.PING_LINE
    assert messages.PING_PREFIX == core_session.PING_PREFIX


def build_inboxes(base):
    """Rows put in the inboxes of synthetic sessions with chosen ages (minutes), measured from the moment this runs:
    `prompt` for the prompt reminder, `ages` for the Stop reminder."""
    root = lead_root(base)
    register_lead(root, "lead-a")
    put = {}
    built = now()

    def row(to, kind, minutes_old, key, sender="lead-a"):
        made = messages.make_row(sender, to, kind, f"work {key}", None, built - datetime.timedelta(minutes=minutes_old))
        messages.append_row(state(root), made)
        put[key] = made["id"]

    row("build-a1", "order", 1, "unacked-order")
    row("lead-a", "result", 1, "lead-result", sender="build-a1")
    row("build-a3", "order", 1, "acked-order")
    leads.ack(state(root), "build-a3", put["acked-order"])
    row("young", "order", 5, "young-order")
    row("question", "question", 90, "old-question")
    row("old", "order", 45, "old-order")
    row("oldacked", "order", 45, "old-acked-order")
    leads.ack(state(root), "oldacked", put["old-acked-order"])
    return root, put


@pytest.fixture(scope="module")
def inboxes(tmp_path_factory):
    return build_inboxes(tmp_path_factory.mktemp("inboxes"))


@pytest.mark.parametrize("session, kind", [
    case("a-session-with-an-unacked-item-is-warned", "build-a1", "warn"),
    case("a-session-with-an-acked-item-is-not", "build-a3", "allow"),
    case("a-session-with-nothing-is-not", "build-a2", "allow"),
    case("a-lead-is-left-to-its-own-reminder", "lead-a", "allow"),
])
def test_the_prompt_reminder_reads_the_unacked_rows_of_the_sessions_own_inbox(inboxes, session, kind):
    """Catches: a session never told of an unacked order, told again after it acked, or a lead told twice."""
    root, _put = inboxes
    assert gate_call(gate_message.remind, root, session=session, event="UserPromptSubmit").kind == kind


def test_the_prompt_reminder_names_the_row_with_its_kind_sender_first_line_and_both_commands(inboxes):
    """Catches: a reminder that leaves out which row, from whom, or the commands that read and ack it."""
    root, put = inboxes
    row_id = put["unacked-order"]
    verdict = gate_call(gate_message.remind, root, session="build-a1", event="UserPromptSubmit")
    assert f"{row_id} order from lead-a: work unacked-order (`mkway inbox {row_id}`, then `mkway ack {row_id}`)" in verdict.message


@pytest.mark.parametrize("session, minutes, kind", [
    case("an-order-older-than-the-default-warns", "old", None, "warn"),
    case("an-order-younger-than-the-default-does-not", "young", None, "allow"),
    case("an-old-question-does-not", "question", None, "allow"),
    case("an-old-order-already-acked-does-not", "oldacked", None, "allow"),
    case("a-session-with-no-rows-does-not", "build-a9", None, "allow"),
    case("a-longer-limit-lets-the-old-order-pass", "old", 60, "allow"),
    case("a-shorter-limit-catches-the-young-order", "young", 1, "warn"),
])
def test_the_stop_reminder_reads_the_age_of_unacked_orders_against_the_profiles_minutes(inboxes, session, minutes, kind):
    """Catches: an old unacked order never reminded, a question or acked order reminded, or a limit that ignores the profile."""
    root, _put = inboxes
    profile = profile_of(root) if minutes is None else dict(profile_of(root), messaging={"ack_reminder_minutes": minutes})
    assert gate_call(gate_message.stop, root, session=session, event="Stop", profile=profile).kind == kind


def test_the_ages_of_the_rows_do_not_depend_on_how_long_ago_the_module_was_imported(tmp_path, monkeypatch):
    """Catches: MW-141 (MW141-D1): a row age measured from a clock taken at import, so a run that reaches the test 20
    minutes after collection sees a 45-minute order as 65 minutes old and warns under a 60-minute limit."""
    monkeypatch.setattr(sys.modules[__name__], "NOW", now() - datetime.timedelta(minutes=20), raising=False)
    root, _put = build_inboxes(tmp_path)
    profile = dict(profile_of(root), messaging={"ack_reminder_minutes": 60})
    assert gate_call(gate_message.stop, root, session="old", event="Stop", profile=profile).kind == "allow"


def test_the_stop_reminder_names_the_old_order_and_the_default_age(inboxes):
    """Catches: a reminder that does not name the order or the age limit it applies."""
    root, put = inboxes
    verdict = gate_call(gate_message.stop, root, session="old", event="Stop")
    assert verdict.reason_id == "orders-unacked"
    assert f"{put['old-order']} from lead-a: work old-order (`mkway inbox {put['old-order']}`" in verdict.message
    assert "more than 30 minutes" in verdict.message


# ---- the records step reads the stdout and the nonce store -----------------------------------------------------------------

def post(root, stdout, session="s1", tool="Bash", response=None):
    payload = {"session_id": session, "hook_event_name": "PostToolUse", "tool_name": tool,
               "tool_input": {"command": "python mkway/engine/mkway.py card new x"},
               "tool_response": response if response is not None else {"stdout": stdout, "stderr": "", "interrupted": False}}
    return dispatch.run("PostToolUse", "post", json.dumps(payload), env={"CLAUDE_PROJECT_DIR": str(root)})


def written(root):
    return jsonl(state(root) / "records.jsonl")


@pytest.fixture
def new_card_run(tmp_path):
    """A root where a session ran `card new` (nonce issued, no record yet): (root, stdout, (kind, value, nonce))."""
    root = task_root(tmp_path)
    code, out, _err = cli(root, "card", "new", "First", session=True)
    assert code == 0
    return root, out, core_session.ok_lines(out)[0]


def test_the_command_itself_writes_no_row_before_the_post_group_runs(new_card_run):
    """Catches: a record written by the command from its own command line, before or without the run."""
    root, _out, _claim = new_card_run
    assert written(root) == []


def test_a_line_whose_nonce_was_issued_is_recorded_with_the_session_and_a_time(new_card_run):
    """Catches: a post group that records nothing, or a row without the session id, kind, value or `by: session`."""
    root, out, _claim = new_card_run
    assert post(root, out).exit_code == 0
    (row,) = written(root)
    assert {k: row[k] for k in ("session_id", "kind", "value", "by")} == {
        "session_id": "s1", "kind": "new", "value": "CARD-001", "by": "session"}
    assert row["time"]


def test_a_line_with_no_nonce_file_writes_no_record(tmp_path):
    """Catches: a post group that trusts the stdout text alone."""
    root = task_root(tmp_path)
    post(root, "mkway-ok search anything " + "0" * 32 + "\n")
    assert written(root) == []


def test_a_nonce_issued_for_another_kind_writes_no_record(new_card_run):
    """Catches: a post group that accepts a nonce for a kind it was not issued for."""
    root, _out, (_kind, value, nonce) = new_card_run
    post(root, f"mkway-ok take {value} {nonce}\n")
    assert written(root) == []


def test_a_nonce_issued_for_another_value_writes_no_record(new_card_run):
    """Catches: a post group that accepts a nonce for a value it was not issued for."""
    root, _out, (_kind, _value, nonce) = new_card_run
    post(root, f"mkway-ok new CARD-009 {nonce}\n")
    assert written(root) == []


def test_a_replayed_line_is_recorded_once(new_card_run):
    """Catches: a post group that does not use the nonce up, so a replay writes a second record."""
    root, out, _claim = new_card_run
    post(root, out)
    post(root, out)
    assert [r["kind"] for r in written(root)] == ["new"]


def test_a_powershell_string_response_is_read_like_a_bash_stdout(new_card_run):
    """Catches: a post group that reads only the Bash `stdout` key."""
    root, out, _claim = new_card_run
    post(root, None, tool="PowerShell", response=out)
    assert [r["kind"] for r in written(root)] == ["new"]


def test_a_record_that_cannot_be_written_allows_with_a_warn_row(new_card_run):
    """Catches: a post group that lets the session believe it recorded (R271c-D1), a reason that does not name the path, or a failure with no `post-record-failed` refuse row."""
    root, out, _claim = new_card_run
    (state(root) / "records.jsonl").mkdir()
    res = post(root, out)
    assert res.exit_code == 0
    assert "deny" not in res.stdout
    assert '"block"' in res.stdout
    assert "records.jsonl" in res.stdout
    assert [(r["gate"], r["reason_id"], r["kind"]) for r in jsonl(state(root) / "refusals.jsonl")] == [
        ("records", "post-record-failed", "refuse")]


def test_a_new_card_of_a_session_gets_its_orderer_cell_in_the_register(tmp_path):
    """Catches: a card a session wrote that keeps reading `owner` in the register's `Ordered by` column (MW-011)."""
    root = lead_root(tmp_path)
    code, out, _err = cli(root, "card", "new", "Second", session=True)
    assert code == 0
    assert post(root, out, session="builder-9").exit_code == 0
    assert register.find(register.read(root, profile_of(root)), "CARD-001")[register.ORDERED] == "builder-9"


def test_the_regex_of_an_ok_line_is_the_one_the_nonce_store_issues_for():
    """Catches: two copies of the `mkway-ok` line shape that drift apart, so a claim the engine prints is never read."""
    assert (records.OK_LINE.pattern, records.OK_LINE.flags) == (core_session.OK_LINE.pattern, core_session.OK_LINE.flags)


def test_a_failed_agent_record_is_a_warn_row_and_never_a_block(tmp_path):
    """Catches: an agent start that goes on although its record cannot be written (R271c-D1), or a refusal that does not name agents.jsonl."""
    root = task_root(tmp_path)
    (state(root) / "agents.jsonl").mkdir()
    payload = {"session_id": "s1", "hook_event_name": "SubagentStart", "cwd": str(root), "agent_id": "a1",
               "agent_type": "worker", "transcript_path": "unused.jsonl"}
    res = dispatch.run("SubagentStart", "post", json.dumps(payload), env={"CLAUDE_PROJECT_DIR": str(root)})
    assert (res.exit_code, "agents.jsonl" in res.stderr) == (2, True)
    assert [(r["reason_id"], r["kind"]) for r in jsonl(state(root) / "refusals.jsonl")] == [("agent-record-failed", "refuse")]


# ---- the wiring: the manifest and the dispatcher ---------------------------------------------------------------------------

def entries(gate_name):
    return [e for e in dispatch.load_manifest(dispatch.ENGINE_DIR) if e.get("gate") == gate_name]


def reasons_of(module):
    found = set()
    for e in dispatch.load_manifest(dispatch.ENGINE_DIR):
        if (e.get("function") or ":").split(":")[0] == module:
            found |= set(e.get("reason_ids", ()))
    return found


@pytest.mark.parametrize("module, reasons", [
    case("subtask", "gate_subtask", core_session.SUBTASK_REASONS), case("lead", "gate_lead", core_session.LEAD_REASONS),
    case("message", "gate_message", core_session.MESSAGE_REASONS), case("records", "gate_records", core_session.RECORD_REASONS),
    case("agents", "gate_agents", core_session.AGENT_REASONS)])
def test_the_manifest_declares_exactly_the_reasons_the_core_can_return(module, reasons):
    """Catches: a reason the core returns that no manifest entry declares, or a declared reason the core can never return."""
    assert reasons_of(module) == set(reasons)


@pytest.mark.parametrize("name, wanted", [
    case("lead-edit", "lead.edit", dict(function="gate_lead:edit", group="edit", event="PreToolUse", onFailure="block",
                                        matcher="Edit|Write|MultiEdit|NotebookEdit", **{"class": "form"})),
    case("lead-shell", "lead.shell", dict(function="gate_lead:shell", group="shell", event="PreToolUse", onFailure="block",
                                          matcher="Bash|PowerShell", **{"class": "form"})),
    case("lead-remind", "lead.remind", dict(function="gate_lead:remind", group="prompt", event="UserPromptSubmit",
                                            onFailure="none", **{"class": "form"})),
    case("message-send", "message.send", dict(function="gate_message:check", group="message", event="PreToolUse",
                                              onFailure="none", matcher="SendMessage", **{"class": "form"})),
    case("message-remind", "message.remind", dict(function="gate_message:remind", group="prompt", event="UserPromptSubmit",
                                                  onFailure="none", **{"class": "form"})),
    case("message-stop", "message.stop", dict(function="gate_message:stop", group="stop", event="Stop", onFailure="none",
                                              **{"class": "form"})),
])
def test_each_session_form_entry_is_wired_to_its_shell_function_and_event(name, wanted):
    """Checks: each session form entry points at its function, group, event and matcher, and fails closed where it must fail open (lead.edit and lead.shell expect block), not open."""
    (entry,) = [e for e in dispatch.load_manifest(dispatch.ENGINE_DIR) if e["name"] == name]
    assert {k: entry.get(k) for k in wanted} == wanted
    assert entry["default_on"] is True
    assert entry["status"] == "on"


@pytest.mark.parametrize("group, first", [case("edit-group", "edit", "lead.edit"), case("shell-group", "shell", "lead.shell")])
def test_the_lead_entries_come_before_every_other_entry_of_their_group(group, first):
    """Catches: a lead refusal that reads `no-open-card` because another gate of the group ran first."""
    manifest = dispatch.load_manifest(dispatch.ENGINE_DIR)
    assert [e["name"] for e in manifest if e["group"] == group and e.get("function")][0] == first


@pytest.mark.parametrize("gate_name", [case("lead", "lead"), case("message", "message")])
def test_the_gate_class_is_form(gate_name):
    """Catches: a gate that blocks from the first install instead of starting in watch mode."""
    assert gatemode.gate_class(dispatch.load_manifest(dispatch.ENGINE_DIR), gate_name) == gatemode.FORM


@pytest.mark.parametrize("gate_name", [case("lead", "lead"), case("message", "message")])
def test_a_first_install_starts_the_gate_in_watch(gate_name):
    """Catches: a form gate of this family left out of the install's watch rule (MW-012 rule 5)."""
    manifest = dispatch.load_manifest(dispatch.ENGINE_DIR)
    watched = {e.get("gate", e["name"]) for e in manifest if install._loadable_on(make_profile(), e)
               and gatemode.gate_class(manifest, e.get("gate", e["name"])) == gatemode.FORM}
    assert gate_name in watched


def test_install_generates_one_hook_entry_for_the_message_gate_with_the_sendmessage_matcher():
    """Catches: a message gate that the install never hooks, or hooks on the wrong tool."""
    manifest = dispatch.load_manifest(dispatch.ENGINE_DIR)
    (found,) = [e for e in install.generate_entries(make_profile(), manifest) if e["group"] == "message"]
    assert found["matcher"] == "SendMessage"
    assert "hook PreToolUse --group message" in found["command"]


def test_the_switch_gates_message_on_false_drops_the_hook_entry():
    """Catches: a profile switch that does nothing for the message gate."""
    manifest = dispatch.load_manifest(dispatch.ENGINE_DIR)
    off = install.generate_entries(make_profile(gates={"message": {"on": False}}), manifest)
    assert [e for e in off if e["group"] == "message"] == []


def hook(root, group, tool_input, tool, session, manifest_entries):
    payload = {"session_id": session, "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input,
               "cwd": str(root)}
    return dispatch.run("PreToolUse", group, json.dumps(payload),
                        env={"CLAUDE_PROJECT_DIR": str(root), "CLAUDECODE": "1"}, manifest=manifest_entries)


@pytest.fixture
def lead_watch(tmp_path):
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    return root, [e for e in entries("lead") if e["name"] in ("lead.edit", "lead.shell")]


def refusals(root, kind):
    return [(r["reason_id"], r["session"]) for r in jsonl(state(root) / "refusals.jsonl") if r.get("kind") == kind]


def test_a_lead_edit_refusal_is_a_deny_before_the_watch_marker(lead_watch):
    """Catches: a lead refusal that reaches the session as anything but a deny with the reason id."""
    root, manifest_entries = lead_watch
    out = hook(root, "edit", {"file_path": "src/app.py", "content": "x"}, "Write", "lead-a", manifest_entries)
    assert json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "lead-no-edit" in out.stdout


def test_a_lead_edit_refusal_in_watch_mode_is_a_would_refuse_row_and_the_call_goes_ahead(lead_watch):
    """Catches: a watch marker that still blocks, or that logs no row with the reason id and the session."""
    root, manifest_entries = lead_watch
    gatemode.write_marker(state(root), "lead", "installed")
    out = hook(root, "edit", {"file_path": "src/app.py", "content": "x"}, "Write", "lead-a", manifest_entries)
    assert (out.exit_code, out.stdout) == (0, "")
    assert refusals(root, "would-refuse") == [("lead-no-edit", "lead-a")]


def test_a_lead_card_take_in_watch_mode_is_a_would_refuse_row_with_its_own_reason(lead_watch):
    """Catches: a watch-mode row for `card take` that carries another reason id."""
    root, manifest_entries = lead_watch
    gatemode.write_marker(state(root), "lead", "installed")
    out = hook(root, "shell", {"command": "python mkway/engine/mkway.py card take CARD-001"}, "Bash", "lead-a", manifest_entries)
    assert out.stdout == ""
    assert refusals(root, "would-refuse") == [("lead-no-take", "lead-a")]


def test_gate_on_lead_ends_watch_mode(lead_watch):
    """Catches: an owner command `mkway gate on lead` that leaves the gate in watch mode."""
    root, _manifest_entries = lead_watch
    gatemode.write_marker(state(root), "lead", "installed")
    assert cli(root, "gate", "on", "lead")[0] == 0
    assert not gatemode.is_watching(state(root), "lead")


def test_a_message_refusal_is_a_deny_before_the_watch_marker(mail):
    """Catches: a message refusal (MW-110: the second ping of one row) that reaches the session as anything but a deny with the reason id."""
    root, rows = mail
    out = hook(root, "message", {"to": "x", "message": f"mkway inbox {rows['pinged']}"}, "SendMessage", "lead-a",
               [e for e in entries("message") if e["name"] == "message.send"])
    assert json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "message-duplicate" in out.stdout


def test_free_text_over_send_message_passes_the_hook_and_records_no_ping(mail):
    """Catches: MW-110: free text over SendMessage refused by the real dispatcher, or recorded as a ping."""
    root, _rows = mail
    before = pings(root)
    out = hook(root, "message", {"to": "x", "message": "just words"}, "SendMessage", "lead-a",
               [e for e in entries("message") if e["name"] == "message.send"])
    assert (out.exit_code, out.stdout) == (0, "")
    assert pings(root) == before


def test_a_message_refusal_in_watch_mode_is_a_would_refuse_row_and_records_no_ping(mail):
    """Catches: a watch-mode message refusal (MW-110: the second ping of one row) that blocks, logs the wrong reason, or records a ping for the refused call."""
    root, rows = mail
    before = pings(root)
    gatemode.write_marker(state(root), "message", "installed")
    out = hook(root, "message", {"to": "x", "message": f"mkway inbox {rows['pinged']}"}, "SendMessage", "lead-a",
               [e for e in entries("message") if e["name"] == "message.send"])
    assert (out.exit_code, out.stdout) == (0, "")
    assert refusals(root, "would-refuse") == [("message-duplicate", "lead-a")]
    assert pings(root) == before


def test_a_good_ping_in_watch_mode_passes_and_is_recorded(mail):
    """Catches: a watch marker that stops a good ping from being recorded, so its duplicate passes later."""
    root, rows = mail
    gatemode.write_marker(state(root), "message", "installed")
    try:
        out = hook(root, "message", {"to": "x", "message": f"mkway inbox {rows['watched']}"}, "SendMessage", "lead-a",
                   [e for e in entries("message") if e["name"] == "message.send"])
    finally:
        assert cli(root, "gate", "on", "message")[0] == 0
    assert out.stdout == ""
    assert pings(root)[-1]["id"] == rows["watched"]

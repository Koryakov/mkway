"""Card MW-055, rows E1 to E6: a session whose writes are refused can still report. `mkway send --text "<body>"` puts the
message into the inbox itself and prints the ping line; the message gate takes that ping line as for a body-file send.
Layers: the decision as a table, the CLI on a temp root, the gate on the printed line. Synthetic roots only."""
import pytest

from _engine import cli, gate_call
from _mw018 import id_of, ping_of, reason_of, rows_of, send, session_run, state, world
import gate_lock
import gate_message
import gate_records
import gate_subtask
import messages


def text_send(root, sender, to, kind, text, gate_text=None):
    """A session's `mkway send --text "<text>"` as the hooks run it: the lock gate judges the quoted command line
    (`gate_text` stands in for it when the CLI itself is under test), the CLI gets the literal text, then the record
    step. Returns (code, out, err); a gate refusal is (None, "", "<reason id>: <message>")."""
    command = f'python mkway/engine/mkway.py send --to {to} --kind {kind} --text "{gate_text or text}"'
    verdict = gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": command}, session=sender)
    if verdict.kind == "refuse":
        return None, "", f"{verdict.reason_id}: {verdict.message}"
    code, out, err = cli(root, "send", "--to", to, "--kind", kind, "--text", text, session=True)
    if code == 0:
        gate_call(gate_records.record, root, tool="Bash", tool_response={"stdout": out}, session=sender,
                  event="PostToolUse")
    return code, out, err

# (text, the problem is None): the content of a quoted argument is literal (MW-048); expansion is not
TABLE = [
    ("a question about the card", True),
    ("it's (fine); a|b > c", True),
    ("cost is 5$ or $ alone", True),
    ("none of my writes are allowed, I cannot save the report", True),
    ("see $(whoami)", False),
    ("run `date` now", False),
    ("the $HOME folder", False),
    ("the ${HOME} folder", False),
    ("the $1 argument", False),
    ("trailing $", True),
]


@pytest.mark.parametrize("text, plain", TABLE)
def test_the_text_decision_table(text, plain):
    """Checks: a text is taken when it holds no expansion, and the refusal says what is wrong and names --file (E1)."""
    problem = messages.text_problem(text)
    assert (problem is None) == plain, (text, problem)
    assert plain or "--file" in problem, (text, problem)


def test_send_text_writes_the_same_row_as_a_body_file(tmp_path):
    """Checks: --text makes the row a body-file send makes, the same fields and the body as the text (E2)."""
    root = world(tmp_path)
    code, out_file, err = send(root, "build-a1", "lead-a", "result", "the report")
    assert code == 0, err
    code, out_text, err = text_send(root, "build-a1", "lead-a", "result", "the report")
    assert code == 0, err
    first, second = rows_of(root, "lead-a")
    assert list(first) == list(second)
    assert first["id"] == id_of(out_file)
    assert second["id"] == id_of(out_text)
    assert (second["from"], second["to"], second["kind"], second["reply_to"], second["ack_ts"], second["body"]) == (
        "build-a1", "lead-a", "result", None, None, first["body"])
    assert ping_of(out_text) == f"mkway inbox {second['id']}"


@pytest.mark.parametrize("text", [
    pytest.param("see $(whoami)", id="subshell"),
    pytest.param("run `date`", id="backtick"),
    pytest.param("the $HOME folder", id="name"),
])
def test_a_text_with_expansion_is_refused_and_names_the_file_route(tmp_path, text):
    """Catches: an expansion in --text that is not refused as message-text-unsafe with the --file route, or that writes a row (E3)."""
    root = world(tmp_path)
    code, _out, err = text_send(root, "build-a1", "lead-a", "notice", text, gate_text="x")
    assert code != 0
    assert reason_of(err) == "message-text-unsafe"
    assert "--file" in err, (text, err)
    assert rows_of(root, "lead-a") == []


@pytest.mark.parametrize("extra", [
    pytest.param(("--file", "body.txt", "--text", "x"), id="both"),
    pytest.param((), id="neither"),
])
def test_exactly_one_of_file_and_text(tmp_path, extra):
    """Catches: a send with both --file and --text, or with neither, that is not a usage error or that writes a row (E4)."""
    root = world(tmp_path)
    (root / "body.txt").write_text("text", encoding="utf-8")
    base = ("send", "--to", "lead-a", "--kind", "notice")
    code, _out, err = session_run(root, "build-a1", *base, *extra)
    assert code != 0
    assert "--text" in err or "--file" in err, extra
    assert rows_of(root, "lead-a") == []
    code, _out, err = cli(root, *base, "--text", "x")  # the owner's terminal has no inbox: `--text` changes nothing
    assert code != 0
    assert reason_of(err) == "send-session-only"


@pytest.mark.parametrize("reason", ["no-open-card", "card-not-open"])
def test_the_refusal_texts_name_the_text_route(tmp_path, reason):
    """Catches: a refusal of the subtask gate that does not name the --text route of mkway send (E5; MW-110 removed the
    message gate's refusal, so free text passes there and needs no route)."""
    root = world(tmp_path)
    verdicts = {
        "no-open-card": gate_call(gate_subtask.check, root, tool="Edit", tool_input={"file_path": "src/a.py"},
                                  session="free-1"),
        "card-not-open": gate_call(gate_subtask.check, root, tool="Edit", tool_input={"file_path": "src/a.py"},
                                   session="build-a1"),
    }
    verdict = verdicts[reason]
    assert verdict.kind == "refuse"
    assert verdict.reason_id == reason, (reason, verdict)
    assert "--text" in verdict.message, (reason, verdict.message)
    assert "mkway send" in verdict.message, (reason, verdict.message)


def test_the_ping_line_of_a_text_send_passes_the_message_gate(tmp_path):
    """Checks: the ping line of a --text send is allowed once from the sender and then refused as a duplicate; from another session it passes unrecorded (E6; MW-110)."""
    root = world(tmp_path)
    code, out, err = text_send(root, "free-1", "lead-a", "question", "may I")
    assert code == 0, err
    ping = ping_of(out)
    call = dict(tool="SendMessage", tool_input={"message": ping})
    assert gate_call(gate_message.check, root, session="free-2", **call).kind == "allow"
    assert gate_call(gate_message.check, root, session="free-1", **call).kind == "allow"
    assert gate_call(gate_message.check, root, session="free-1", **call).reason_id == "message-duplicate"

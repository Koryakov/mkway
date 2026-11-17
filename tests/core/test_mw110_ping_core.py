"""Card MW-110 (ruling R279a): a SendMessage counts as the ping of an inbox write only when its text is exactly
`mkway inbox <id>` for that write's id (a final line break allowed). Table tests on `core_ping.decide_stop`: no disk, no
clock. One test id is one case. Synthetic values only."""
import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_ping as core
from _no_io import no_io

START = "2026-11-12T10:00:00.000Z"


def use(cid, name, ts, **tool_input):
    return {"type": "assistant", "timestamp": ts,
            "message": {"content": [{"type": "tool_use", "id": cid, "name": name, "input": tool_input}]}}


def result(cid, ts="2026-11-12T10:00:03.000Z"):
    return {"type": "user", "timestamp": ts,
            "message": {"content": [{"type": "tool_result", "tool_use_id": cid, "content": "ok"}]}}


def message(text, ts="2026-11-12T10:00:05.000Z", cid="p1"):
    return use(cid, "SendMessage", ts, to="dd-lead", message=text)


def write(id_="m-1", ts="2026-11-12T10:00:02.000+00:00"):
    return {"id": id_, "from": "b1", "to": "63fcc7cf", "kind": "result", "ts": ts, "name": "dd-lead"}


CALL = (use("t1", "Bash", "2026-11-12T10:00:01.000Z", command="python mkway/engine/mkway.py send --to x"), result("t1"))


def stop(entries, writes):
    facts = core.PingFacts(session_id="b1", entries=tuple(entries), writes=tuple(writes), turn_start=START)
    with no_io():
        return core.decide_stop(facts)


def case(id_, *values):
    return pytest.param(*values, id=id_)


@pytest.mark.parametrize("text, kind", [
    case("the-exact-line-passes", "mkway inbox m-1", "allow"),
    case("a-final-line-break-passes", "mkway inbox m-1\n", "allow"),
    case("a-final-crlf-passes", "mkway inbox m-1\r\n", "allow"),
    case("a-leading-space-is-refused", " mkway inbox m-1", "refuse"),
    case("a-trailing-space-is-refused", "mkway inbox m-1 ", "refuse"),
    case("two-final-line-breaks-are-refused", "mkway inbox m-1\n\n", "refuse"),
    case("a-leading-line-break-is-refused", "\nmkway inbox m-1", "refuse"),
    case("a-case-change-of-the-prefix-is-refused", "MKWAY inbox m-1", "refuse"),
    case("a-case-change-of-the-id-is-refused", "mkway inbox M-1", "refuse"),
    case("another-id-is-refused", "mkway inbox m-2", "refuse"),
    case("the-id-with-more-characters-is-refused", "mkway inbox m-10", "refuse"),
    case("free-text-is-refused", "the report is in your inbox", "refuse"),
    case("the-line-with-more-words-is-refused", "mkway inbox m-1 please read it", "refuse"),
    case("the-line-after-words-is-refused", "please read: mkway inbox m-1", "refuse"),
    case("the-prefix-alone-is-refused", "mkway inbox", "refuse"),
    case("an-empty-text-is-refused", "", "refuse"),
])
def test_only_the_exact_ping_line_of_the_write_counts(text, kind):
    """Catches: any SendMessage taken as the ping (R279a): a ping for another row, free text, or the line with words around
    it lets the Stop pass; the refusal names the write's own ping line."""
    got = stop([*CALL, message(text)], [write()])
    assert got.kind == kind
    if kind == "refuse":
        assert got.reason == "ping-not-sent"
        assert "mkway inbox m-1" in got.text


def test_a_send_message_with_no_text_does_not_count():
    """Catches: a SendMessage with no `message` field (a pure subscription or a malformed call) taken as a ping."""
    entries = [*CALL, use("p1", "SendMessage", "2026-11-12T10:00:05.000Z", to="dd-lead", notify_when_idle=True)]
    assert stop(entries, [write()]).kind == "refuse"


def test_a_message_that_is_not_text_does_not_count():
    """Catches: a non-text `message` value (a number, a list) taken as a ping."""
    entries = [*CALL, use("p1", "SendMessage", "2026-11-12T10:00:05.000Z", to="dd-lead", message=["mkway inbox m-1"])]
    assert stop(entries, [write()]).kind == "refuse"


def test_a_ping_of_the_first_write_leaves_the_second_one_to_ping():
    """Catches: one ping that covers two writes: only the write whose own line was sent is answered, the other is named."""
    entries = [*CALL, message("mkway inbox m-1", ts="2026-11-12T10:00:04.000Z"),
               use("t2", "Bash", "2026-11-12T10:00:06.000Z", command="python mkway/engine/mkway.py send --to x"),
               result("t2", ts="2026-11-12T10:00:08.000Z")]
    got = stop(entries, [write(), write(id_="m-2", ts="2026-11-12T10:00:07.000+00:00")])
    assert got.kind == "refuse"
    assert "mkway inbox m-2" in got.text
    assert "mkway inbox m-1" not in got.text


def test_the_ping_of_a_later_write_does_not_answer_an_earlier_one_sent_after_it_was_written():
    """Catches: a ping line of the second write, sent after both writes, taken as the ping of the first as well."""
    entries = [*CALL, use("t2", "Bash", "2026-11-12T10:00:04.000Z", command="python mkway/engine/mkway.py send --to x"),
               result("t2", ts="2026-11-12T10:00:05.000Z"), message("mkway inbox m-2", ts="2026-11-12T10:00:09.000Z")]
    got = stop(entries, [write(), write(id_="m-2", ts="2026-11-12T10:00:04.500+00:00")])
    assert got.kind == "refuse"
    assert "mkway inbox m-1" in got.text
    assert "mkway inbox m-2" not in got.text

"""Card MW-018, part 4, rows E9 to E11: what a session is told about its unacked items (the start block, the prompt, the
Stop reminder) and the board the owner reads. A reminder never blocks. Synthetic roots and session ids only."""
import datetime

from _engine import cli, gate_call
from _mw018 import id_of, inbox, lines, profile_of, send, session_run, state, world
import gate_message
import messages
import startline


def put(root, to, kind, minutes_old, sender="lead-a", body="some work"):
    """A row in the inbox of `to`, as old as asked (a row the engine wrote `minutes_old` minutes ago)."""
    when = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes_old)
    row = messages.make_row(sender, to, kind, body, None, when)
    messages.append_row(state(root), row)
    return row


def block(root, session, profile=None):
    profile = profile or profile_of(root)
    return startline.render(root, root / "mkway" / "profile.json", profile, [], [], {}, session=session)


# --- E7: the start block and the prompt --------------------------------------------------------------------------

def test_the_start_block_lists_the_unacked_items_of_a_session(tmp_path):
    """Checks: a session with unacked rows has the line `inbox: unacked items: N` with one line per row naming the open and ack commands; an acked row and a row-less session see nothing; a lead's start line lists the rows too (E9)."""
    root = world(tmp_path)
    code, out, err = send(root, "lead-a", "build-a1", "order", "build the thing")
    assert code == 0, err
    row_id = id_of(out)
    text = block(root, "build-a1")
    assert "inbox: unacked items: 1" in text
    assert row_id in text
    assert "order" in text
    assert "lead-a" in text
    assert f"mkway inbox {row_id}" in text
    assert f"mkway ack {row_id}" in text
    assert "inbox: unacked" not in block(root, "build-a2")
    code, out, err = send(root, "build-a1", "lead-a", "result", "built")
    assert code == 0, err
    assert id_of(out) in block(root, "lead-a")
    assert session_run(root, "build-a1", "ack", row_id)[0] == 0
    assert "inbox: unacked" not in block(root, "build-a1")


# --- E8: the Stop reminder ---------------------------------------------------------------------------------------


# --- E9: the board -----------------------------------------------------------------------------------------------

def test_the_board_shows_inboxes_cards_and_asks_in_one_view(tmp_path):
    """Checks: `mkway board` prints the three parts, inboxes, cards and asks, for a session and for the owner's terminal alike, and writes nothing (E11)."""
    root = world(tmp_path)
    code, out, err = send(root, "lead-a", "build-a1", "order", "build the thing")
    assert code == 0, err
    row_id = id_of(out)
    put(root, "lead-a", "result", 3, sender="build-a2", body="all done here")
    before = sorted(p.name for p in (state(root) / "inbox").iterdir()), lines(state(root) / "inbox" / "build-a1.jsonl")
    code, shown, err = session_run(root, "free-1", "board")
    assert code == 0, err
    owner_code, owner_shown, _err = cli(root, "board")
    assert owner_code == 0
    assert owner_shown == shown
    rows = shown.splitlines()
    assert [r for r in rows if not r.startswith(" ")] == ["inboxes:", "cards:", "asks:"]
    build = [r for r in rows if r.startswith("  build-a1")]
    assert len(build) == 1
    assert "builder of lead-a" in build[0]
    assert "unacked 1" in build[0]
    assert "orders 1" in build[0]
    lead = [r for r in rows if r.startswith("  lead-a")]
    assert lead
    assert "lead" in lead[0]
    assert "unacked 1" in lead[0]
    assert f"root {root}" in lead[0]
    assert any(row_id in r and "order" in r and "lead-a" in r and "build the thing" in r for r in rows)
    assert any("all done here" in r and "result" in r for r in rows)
    assert any(r.startswith("  ") and "ordered by lead-a" in r and "held by build-a1" in r and "proposed" in r
               for r in rows)
    assert rows[-1] == "  no ask files"
    assert before == (sorted(p.name for p in (state(root) / "inbox").iterdir()),
                      lines(state(root) / "inbox" / "build-a1.jsonl"))
    assert not (state(root) / "records.jsonl").exists() or all(
        r.get("kind") != "board" for r in lines(state(root) / "records.jsonl"))


def test_the_board_with_nothing_on_it_says_so(tmp_path):
    """Checks: an empty state gives the three headings, each with a line that says there is nothing (E11)."""
    from _engine import task_root
    root = task_root(tmp_path)
    code, shown, err = cli(root, "board")
    assert code == 0, err
    assert shown.splitlines()[0] == "inboxes:"
    assert "no session" in shown
    assert "no card" in shown
    assert "no ask files" in shown

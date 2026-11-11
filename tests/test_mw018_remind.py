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
    """E9: a session with unacked rows in its inbox has the line `inbox: unacked items: N` with one line for each (id,
    kind, sender) naming `mkway inbox <id>` and `mkway ack <id>`; an acked row, and a session with no row, see nothing;
    a lead's own start line (MW-017) lists the rows too."""
    root = world(tmp_path)
    code, out, err = send(root, "lead-a", "build-a1", "order", "build the thing")
    assert code == 0, err
    row_id = id_of(out)
    text = block(root, "build-a1")
    assert "inbox: unacked items: 1" in text and row_id in text and "order" in text and "lead-a" in text
    assert f"mkway inbox {row_id}" in text and f"mkway ack {row_id}" in text
    assert "inbox: unacked" not in block(root, "build-a2")
    code, out, err = send(root, "build-a1", "lead-a", "result", "built")
    assert code == 0, err
    assert id_of(out) in block(root, "lead-a")
    assert session_run(root, "build-a1", "ack", row_id)[0] == 0
    assert "inbox: unacked" not in block(root, "build-a1")


def test_the_prompt_reminds_a_session_of_its_unacked_items_and_never_blocks(tmp_path):
    """E9: at the prompt a session that is no lead gets a warn `inbox-unacked` naming each id with `mkway inbox <id>`
    and `mkway ack <id>`; nothing to say is an allow; a lead is left to its own reminder (`lead-notices-unacked`), so
    it is not told twice."""
    root = world(tmp_path)
    assert gate_call(gate_message.remind, root, session="build-a1", event="UserPromptSubmit").kind == "allow"
    code, out, err = send(root, "lead-a", "build-a1", "order", "build the thing")
    assert code == 0, err
    row_id = id_of(out)
    verdict = gate_call(gate_message.remind, root, session="build-a1", event="UserPromptSubmit")
    assert verdict.kind == "warn" and verdict.reason_id == "inbox-unacked"
    assert f"mkway inbox {row_id}" in verdict.message and f"mkway ack {row_id}" in verdict.message
    code, out, err = send(root, "build-a1", "lead-a", "result", "built")
    assert code == 0, err
    assert gate_call(gate_message.remind, root, session="lead-a", event="UserPromptSubmit").kind == "allow"
    assert session_run(root, "build-a1", "ack", row_id)[0] == 0
    assert gate_call(gate_message.remind, root, session="build-a1", event="UserPromptSubmit").kind == "allow"


# --- E8: the Stop reminder ---------------------------------------------------------------------------------------

def test_a_stop_with_an_old_unacked_order_gets_a_reminder_never_a_block(tmp_path):
    """E10: a Stop with an unacked `order` older than `messaging.ack_reminder_minutes` (default 30) warns
    `orders-unacked` naming the id; a younger order, an acked one, a question of any age and another session's order
    give nothing; the key moves the age; the verdict is never a refusal."""
    root = world(tmp_path)

    def stop(session, profile=None):
        return gate_call(gate_message.stop, root, session=session, event="Stop", profile=profile)

    assert stop("build-a1").kind == "allow"
    young = put(root, "build-a1", "order", 5)
    put(root, "build-a1", "question", 90)
    assert stop("build-a1").kind == "allow"
    old = put(root, "build-a1", "order", 45)
    verdict = stop("build-a1")
    assert verdict.kind == "warn" and verdict.reason_id == "orders-unacked"
    assert old["id"] in verdict.message and young["id"] not in verdict.message
    assert f"mkway inbox {old['id']}" in verdict.message and f"mkway ack {old['id']}" in verdict.message
    assert stop("build-a2").kind == "allow"
    assert stop("build-a1", dict(profile_of(root), messaging={"ack_reminder_minutes": 60})).kind == "allow"
    assert stop("build-a1", dict(profile_of(root), messaging={"ack_reminder_minutes": 1})).kind == "warn"
    assert session_run(root, "build-a1", "ack", old["id"])[0] == 0
    assert stop("build-a1").kind == "allow"


# --- E9: the board -----------------------------------------------------------------------------------------------

def test_the_board_shows_inboxes_cards_and_asks_in_one_view(tmp_path):
    """E11: `mkway board` prints three parts: `inboxes:` (one line for each session: its role, its folder, its unacked
    count and the orders among them, then a line for each unacked row), `cards:` (id, status, who ordered it, who holds
    it) and `asks:` (the ask board). A session and the owner's terminal may run it; it writes nothing."""
    root = world(tmp_path)
    code, out, err = send(root, "lead-a", "build-a1", "order", "build the thing")
    assert code == 0, err
    row_id = id_of(out)
    put(root, "lead-a", "result", 3, sender="build-a2", body="all done here")
    before = sorted(p.name for p in (state(root) / "inbox").iterdir()), lines(state(root) / "inbox" / "build-a1.jsonl")
    code, shown, err = session_run(root, "free-1", "board")
    assert code == 0, err
    owner_code, owner_shown, _err = cli(root, "board")
    assert owner_code == 0 and owner_shown == shown
    rows = shown.splitlines()
    assert [r for r in rows if not r.startswith(" ")] == ["inboxes:", "cards:", "asks:"]
    build = [r for r in rows if r.startswith("  build-a1")]
    assert len(build) == 1 and "builder of lead-a" in build[0] and "unacked 1" in build[0] and "orders 1" in build[0]
    lead = [r for r in rows if r.startswith("  lead-a")]
    assert lead and "lead" in lead[0] and "unacked 1" in lead[0] and f"root {root}" in lead[0]
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
    """E11: an empty state gives the three headings with a line each that says there is nothing."""
    from _engine import task_root
    root = task_root(tmp_path)
    code, shown, err = cli(root, "board")
    assert code == 0, err
    assert shown.splitlines()[0] == "inboxes:" and "no session" in shown and "no card" in shown and "no ask files" in shown

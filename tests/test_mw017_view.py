"""Card MW-017, part 4, rows E17 and E18: the view `mkway leads` with its soft cap, and the order file template
`cards/<id>/ORDER.md`. Synthetic roots and session ids only."""
import re

from _engine import REPO, cli
from _mw017 import lead_root, new_card, profile_of, register_lead, row_of, session_run, state
import cardtool
import leads
import register

HEADINGS = ["## Objective", "## Output form", "## Time-box", "## Boundary"]


def _open_card(root, lead, appetite=None):
    card = new_card(root, lead)
    register.write(root, profile_of(root), lambda rows: [dict(r, status="open") if r["id"] == card else r
                                                         for r in rows])
    if appetite:
        path = cardtool.card_file(root, profile_of(root), card)
        text = re.sub(r"^\| \*\*Appetite\*\* \|.*\|$", lambda _m: f"| **Appetite** | {appetite} |",
                      path.read_text(encoding="utf-8"), flags=re.M)
        path.write_text(text, encoding="utf-8", newline="\n")
    return card


def test_the_view_has_one_line_per_lead(tmp_path):
    """E17: `mkway leads` prints, for each registered lead: its id, the cards it ordered that are not closed, how many
    of those are past their Appetite, its last activity (the last time a state record names it) and its unacked
    notices, then one line for each unacked notice with its id. A session may run it; it changes nothing."""
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    register_lead(root, "lead-b")
    late = _open_card(root, "lead-a", "1 day — from 2000-01-01")
    fine = _open_card(root, "lead-a", "99999 days — from 2000-01-01")
    done = _open_card(root, "lead-a")
    register.write(root, profile_of(root), lambda rows: [dict(r, status="closed") if r["id"] == done else r
                                                         for r in rows])
    notice = leads.append_notice(state(root), "lead-a", "something happened")
    code, out, err = cli(root, "leads")
    assert code == 0, err
    lines = out.splitlines()
    a = next(x for x in lines if x.startswith("lead-a"))
    assert "ordered 2" in a and late in a and fine in a and done not in a
    assert "overdue 1" in a and "unacked 1" in a and "last activity" in a and "not established" not in a
    b = next(x for x in lines if x.startswith("lead-b"))
    assert "ordered 0" in b and "overdue 0" in b and "unacked 0" in b
    assert any(x.strip().startswith("unacked " + notice["id"]) and "something happened" in x for x in lines)
    assert cli(root, "leads", session=True)[0] == 0


def test_the_view_with_no_lead_names_the_commands(tmp_path):
    """E17: with no registered lead the view says so and names the two ways to make one."""
    code, out, _err = cli(lead_root(tmp_path), "leads")
    assert code == 0 and "no registered lead" in out and "mkway lead register" in out and "mkway lead add" in out


def test_the_view_escalates_notices_unacked_past_the_time(tmp_path):
    """E16, E17: a notice unacked for `leads.escalate_hours` shows as `escalated` in the lead's line count."""
    import datetime
    root = lead_root(tmp_path, leads={"escalate_hours": 3})
    register_lead(root, "lead-a")
    now = datetime.datetime.now(datetime.timezone.utc)
    leads.append_notice(state(root), "lead-a", "old", now=now - datetime.timedelta(hours=4))
    leads.append_notice(state(root), "lead-a", "new", now=now - datetime.timedelta(hours=1))
    out = cli(root, "leads")[1]
    a = next(x for x in out.splitlines() if x.startswith("lead-a"))
    assert "unacked 2" in a and "escalated 1" in a


def test_more_open_cards_than_the_cap_is_a_warning_never_a_refusal(tmp_path):
    """E17: a lead with more not-closed cards than `leads.max_cards` (default 5) gets a warning line in the view, naming
    the key; its next `card new` still works. At the cap there is no warning."""
    root = lead_root(tmp_path, leads={"max_cards": 2})
    register_lead(root, "lead-a")
    _open_card(root, "lead-a")
    _open_card(root, "lead-a")
    assert "warning" not in cli(root, "leads")[1]
    _open_card(root, "lead-a")
    out = cli(root, "leads")[1]
    warning = next(x for x in out.splitlines() if x.startswith("warning"))
    assert "lead-a" in warning and "3" in warning and "leads.max_cards" in warning and "2" in warning
    assert session_run(root, "lead-a", "card", "new", "Fourth")[0] == 0
    assert cli(root, "leads")[0] == 0


def test_the_order_template_has_the_four_headings():
    """E18: `cards/_TEMPLATE/ORDER.md` holds the four headings, in this order, each with a line that says what goes
    under it; the card form is not touched; the install set carries the file."""
    text = (REPO / "cards" / "_TEMPLATE" / "ORDER.md").read_text(encoding="utf-8")
    assert [x for x in text.splitlines() if x.startswith("#")][1:] == HEADINGS
    assert text.splitlines()[0].startswith("# ") and "<ID>" in text.splitlines()[0]
    for heading in HEADINGS:
        body = text.split(heading + "\n", 1)[1].split("\n## ", 1)[0].strip()
        assert body, heading
    import install
    assert "cards/_TEMPLATE/ORDER.md" in install.SET_FILES


def test_a_leads_new_card_gets_an_order_file_and_nobody_elses_does(tmp_path):
    """E18: `card new` by a registered lead also writes `<card folder>/ORDER.md` from the template, headed with the
    card id; by a builder or in the owner's terminal it writes only the card file; an existing order file is kept."""
    root = lead_root(tmp_path)
    register_lead(root, "lead-a")
    mine = new_card(root, "lead-a")
    folder = root / row_of(root, mine)["folder"].strip("`")
    order = folder / "ORDER.md"
    text = order.read_text(encoding="utf-8")
    assert text.splitlines()[0] == f"# {mine}: order"
    assert [x for x in text.splitlines() if x.startswith("## ")] == HEADINGS
    theirs = new_card(root, "builder-1", "Theirs")
    assert not (root / row_of(root, theirs)["folder"].strip("`") / "ORDER.md").exists()
    assert cli(root, "card", "new", "Owners")[0] == 0
    assert not list((root / "mkway" / "cards").glob("*Owners*/ORDER.md")) and not list(
        (root / "mkway" / "cards").glob("*owners*/ORDER.md"))
    assert (folder / "CARD.md").is_file()

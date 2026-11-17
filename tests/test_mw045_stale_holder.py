"""Card MW-045: a crashed card holder never blocks the root. `card release <id>` by the owner's terminal or by the
card's orderer session; an automatic release at take time when the holder's last seen is older than `cards.stale_hours`.
Synthetic task roots and synthetic session ids only."""
import datetime
import json
import re

import pytest

import _docs as docs
from _engine import cli, gate_call, jsonl, make_profile, task_root
from test_cardmoves import set_paths
import gate_lock
import logs
import profiles
import records
import register
import sessions

CLI = "python mkway/engine/mkway.py card"
HOLDER, TAKER, ORDERER, THIRD = "abcdefgh-1234", "zzzzzzzz-9999", "orderer0-5555", "thirdsss-7777"


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _state(root):
    return root / "mkway" / "state"


def _log(root, card_id="CARD-001"):
    (folder,) = [p for p in (root / "mkway" / "cards").iterdir() if p.name.startswith(card_id + "-")]
    return (folder / "CARD.md").read_text(encoding="utf-8").split("## 8. Log", 1)[1]


def _lock(root, command, session):
    return gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": command}, session=session)


def _reason(verdict):
    return verdict.reason_id if verdict.kind == "refuse" else "allow"


def _ago(hours):
    return logs.now() - datetime.timedelta(hours=hours)


def _take_at(root, session, card, when):
    """A `take` record written with the given time (records.append stamps now)."""
    row = {"session_id": session, "kind": "take", "value": card, "time": when.isoformat(timespec="milliseconds"),
           "by": "session"}
    with open(_state(root) / records.RECORDS, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row) + "\n")


def _root(tmp_path, *, seen_hours_ago=1.0, hold_hours_ago=1.0, cards=None):
    """A task root whose HOLDER holds CARD-001 (open); CARD-002 is proposed and ordered by ORDERER. `seen_hours_ago`
    is the holder's last row in `sessions.jsonl` (None: no row); `hold_hours_ago` is the time of its take record."""
    root = task_root(tmp_path, cards=dict({"approver": "orderer"}, **(cards or {})))
    assert cli(root, "card", "new", "First")[0] == 0
    assert cli(root, "card", "new", "Second")[0] == 0
    set_paths(root, "CARD-001", "`src/`")
    assert cli(root, "card", "open", "CARD-001")[0] == 0
    register.set_ordered(root, _profile(root), "CARD-001", ORDERER)
    _take_at(root, HOLDER, "CARD-001", _ago(hold_hours_ago))
    if seen_hours_ago is not None:
        sessions.append(_state(root), HOLDER, root, now=_ago(seen_hours_ago))
    return root


def _held(root):
    return records.holders(_state(root), register.closed_ids(root, _profile(root)))


def test_the_owners_terminal_release_frees_a_held_card(tmp_path):
    """E1: the owner's plain `card release <id>` of a card a session holds frees it (no `--force`): no holder, a
    `release` record by the owner, a Log row naming the owner; `--force` frees it too. Catches: an owner who needs a
    flag to free a crashed holder's card."""
    root = _root(tmp_path)
    assert _held(root) == {"CARD-001": HOLDER}
    code, _out, err = cli(root, "card", "release", "CARD-001")
    assert code == 0, err
    assert _held(root) == {}
    last = records.rows(_state(root))[-1]
    assert (last["kind"], last["value"], last["by"]) == ("release", "CARD-001", "owner")
    assert "released by the owner" in _log(root)
    _take_at(root, HOLDER, "CARD-001", _ago(0.5))
    assert cli(root, "card", "release", "CARD-001", "--force")[0] == 0
    assert _held(root) == {}


def test_the_orderer_session_releases_the_card_another_session_holds(tmp_path):
    """E2: the session that ordered the card runs `card release <id>`: the gate allows and leaves a permit, the CLI
    frees the card: no holder, a `release` record by `orderer` that names that session, a Log row naming the orderer.
    Catches: a lead that cannot free a crashed builder's card, or a release that leaves the holder in place."""
    root = _root(tmp_path)
    assert _reason(_lock(root, f"{CLI} release CARD-001", ORDERER)) == "allow"
    code, out, err = cli(root, "card", "release", "CARD-001", session=True)
    assert code == 0, err
    assert _held(root) == {}
    last = records.rows(_state(root))[-1]
    assert (last["kind"], last["value"], last["by"], last["session_id"]) == ("release", "CARD-001", "orderer", ORDERER)
    assert "released by the orderer orderer0" in _log(root)


def test_a_third_session_cannot_release_the_card(tmp_path):
    """E3: a session that is neither the holder nor the orderer is refused `card-not-yours`; the text names the
    orderer; the holder stays; with no permit the CLI frees nothing. Catches: a release open to any session."""
    root = _root(tmp_path)
    v = _lock(root, f"{CLI} release CARD-001", THIRD)
    assert v.kind == "refuse" and v.reason_id == "card-not-yours" and "orderer" in v.message and "--force" in v.message
    code, _out, _err = cli(root, "card", "release", "CARD-001", session=True)
    assert _held(root) == {"CARD-001": HOLDER}
    assert "released by" not in _log(root)


def test_a_stale_holder_is_released_at_take_with_a_log_row(tmp_path):
    """E4: the holder's last seen is older than the default 4 hours: the gate allows the take; the CLI releases the
    holder first (a `release` record by `stale`), writes the Log row `stale holder <8 characters> released` in the
    holder's card, and the take goes on. Catches: a root that stays busy for good after a crash."""
    root = _root(tmp_path, seen_hours_ago=5, hold_hours_ago=6)
    assert _reason(_lock(root, f"{CLI} take CARD-002", TAKER)) == "allow"
    code, out, err = cli(root, "card", "take", "CARD-002", session=True)
    assert code == 0 and "mkway-ok take CARD-002 " in out, err
    assert _held(root) == {}
    stale = [r for r in records.rows(_state(root)) if r.get("by") == "stale"]
    assert len(stale) == 1 and (stale[0]["kind"], stale[0]["value"]) == ("release", "CARD-001")
    assert "stale holder abcdefgh released" in _log(root) and HOLDER not in _log(root)
    records.append(_state(root), TAKER, "take", "CARD-002")  # what the `post` group writes after the take
    assert _held(root) == {"CARD-002": TAKER}


def test_a_fresh_holder_still_refuses_and_the_text_names_both_ways_out(tmp_path):
    """E5: the holder was seen 1 hour ago: the take is still refused `take-root-busy`; the text names `card release
    <card>` by the owner or the orderer and the automatic release after `cards.stale_hours`; the CLI releases nothing
    and writes no Log row. Catches: a stale rule that frees a live builder, or a refusal with one way out."""
    root = _root(tmp_path, seen_hours_ago=1, hold_hours_ago=1)
    v = _lock(root, f"{CLI} take CARD-002", TAKER)
    assert v.kind == "refuse" and v.reason_id == "take-root-busy"
    assert f"card release CARD-001" in v.message and "orderer" in v.message and "cards.stale_hours" in v.message
    assert "abcdefgh" in v.message and "own worktree" in v.message and "hand" in v.message
    assert cli(root, "card", "take", "CARD-002", session=True)[0] == 0
    assert _held(root) == {"CARD-001": HOLDER}
    assert "stale holder" not in _log(root)


def test_the_key_changes_the_hours(tmp_path):
    """E6: a holder last seen 2 hours ago is fresh at the default 4 and stale with `cards.stale_hours` 1. Catches: a
    key that is read and ignored, or a hard-coded figure."""
    fresh = _root(tmp_path / "default", seen_hours_ago=2, hold_hours_ago=2)
    assert _reason(_lock(fresh, f"{CLI} take CARD-002", TAKER)) == "take-root-busy"
    stale = _root(tmp_path / "short", seen_hours_ago=2, hold_hours_ago=2, cards={"stale_hours": 1})
    assert _reason(_lock(stale, f"{CLI} take CARD-002", TAKER)) == "allow"
    longer = _root(tmp_path / "long", seen_hours_ago=5, hold_hours_ago=5, cards={"stale_hours": 8})
    assert _reason(_lock(longer, f"{CLI} take CARD-002", TAKER)) == "take-root-busy"


def test_a_holder_with_no_sessions_row_is_stale_only_by_its_hold_time(tmp_path):
    """E7: with no row in `sessions.jsonl` the holder is stale only when its take record is older than the hours; a
    recent take is fresh. Catches: a missing row read as dead at once."""
    old = _root(tmp_path / "old", seen_hours_ago=None, hold_hours_ago=5)
    assert _reason(_lock(old, f"{CLI} take CARD-002", TAKER)) == "allow"
    recent = _root(tmp_path / "recent", seen_hours_ago=None, hold_hours_ago=1)
    assert _reason(_lock(recent, f"{CLI} take CARD-002", TAKER)) == "take-root-busy"


def test_the_key_is_in_the_schema_the_accessor_and_keys_md():
    """E8: `cards.stale_hours` (a number above 0, default 4; an unusable value reads as 4) is in the schema, the
    accessor and KEYS.md; the schema refuses 0 and text."""
    from _engine import ENGINE
    assert profiles.cards_stale_hours(None) == 4 and profiles.cards_stale_hours(make_profile()) == 4
    assert profiles.cards_stale_hours(make_profile(cards={"stale_hours": 1.5})) == 1.5
    for bad in (0, -1, "x", True, None, [1]):
        assert profiles.cards_stale_hours(make_profile(cards={"stale_hours": bad})) == 4, bad
    assert profiles.validate(make_profile(cards={"stale_hours": 2})) == []
    assert profiles.validate(make_profile(cards={"stale_hours": 0})) != []
    assert profiles.validate(make_profile(cards={"stale_hours": "x"})) != []
    schema = json.loads((ENGINE / "profile.schema.json").read_text(encoding="utf-8"))
    assert schema["properties"]["cards"]["properties"]["stale_hours"]["type"] == "number"
    keys = (ENGINE / "KEYS.md").read_text(encoding="utf-8")
    assert re.search(r"^\| `cards\.stale_hours` \| in schema now \| `cards\.stale_hours` \| .*`4`", keys, re.M)


@pytest.mark.engine_repo  # reads the repository's own README, register and changelog
def test_readme_register_changelog_and_card_name_the_card():
    """E9: the README names `card release` by the owner or the orderer and the stale release; register row; a line
    under `## 0.2.7`; the card folder; VERSION is untouched (0.2.7)."""
    from _engine import REPO
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "`cards.stale_hours`" in readme and "stale holder" in readme and "`card release <id>`" in readme
    register_text = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert re.search(r"^\| MW-045 \| .*\|.*`cards/MW-045-[a-z0-9-]+`", register_text, re.M)
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    top = docs.changelog_section(changelog, "MW-045")
    assert re.search(r"^- MW-045: ", top, re.M)
    assert list((REPO / "cards").glob("MW-045-*/CARD.md"))
    docs.assert_version_file()

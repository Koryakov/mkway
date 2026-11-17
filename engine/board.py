"""What `mkway board` and the start line add for the card board (card MW-112, record R3). The functions that build a line are
pure (their inputs are rows and ids); the readers at the end take them from the state folder, the shared inbox and git, and
a read that fails adds no line: the board never fails here.

- old red: the test ids that were red at HEAD and still are in the last commit record (`old_red` of the last row of
  `commit_tests.jsonl`, written by the this-commit judgement of card MW-108), each with its owner card or, for an orphan,
  «no open card holds it»;
- the age of every unacked inbox item (R270a: it stays on the board until it is acked; the reminder fires once);
- uncommitted files of an open card that a session holds, with the holder and the orderer; the files of a session that
  ended (a stale holder, `cards.stale_hours`) are marked as such;
- `card X: no DONE file`: a card a session holds, with no inbox row of kind `result` written by that session since it took
  the card (the result file a builder sends with `mkway send --file`; a session holds one card at a time, so the sender
  tells the card);
- the agent record that could not be written (R271c), until a later agent row is written.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional

SHOWN = 5  # files named in one line; the rest are counted
AGENT_FAILED = "agent-record-failed"


def _when(text) -> Optional[datetime.datetime]:
    if not isinstance(text, str):
        return None
    try:
        when = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=datetime.timezone.utc)


def old_red_lines(rows) -> list:
    """One line for each old red of the last commit record; none when the last row has no `old_red` or it is not a list of
    `{"test", "card"}` objects (a key absent or empty means no old red)."""
    last = next((r for r in reversed(rows or []) if isinstance(r, dict) and "tree" in r), None)
    found = last.get("old_red") if last else None
    if not isinstance(found, list):
        return []
    out = []
    for item in found:
        if isinstance(item, dict) and isinstance(item.get("test"), str):
            card = item.get("card")
            owner = f"owner card {card}" if isinstance(card, str) and card else "no open card holds it"
            out.append(f"old red: {item['test']} ({owner})")
    return out


def paths_lines(rows, open_ids) -> list:
    """MW-137: one line for each card in `open_ids` whose Paths were re-recorded (rows of `paths_changes.jsonl`: card, old, new,
    by, time): how many times, and the last change with who made it and when. A row with no card or no lists is left out."""
    per: dict = {}
    for row in rows or []:
        if isinstance(row, dict) and isinstance(row.get("card"), str) and isinstance(row.get("old"), list) \
                and isinstance(row.get("new"), list):
            per.setdefault(row["card"], []).append(row)
    out = []
    for card, items in per.items():
        if card not in open_ids:
            continue
        last = items[-1]
        added = sorted(set(map(str, last["new"])) - set(map(str, last["old"])))
        removed = sorted(set(map(str, last["old"])) - set(map(str, last["new"])))
        out.append(f"paths of {card} re-recorded {len(items)} time{'s' if len(items) != 1 else ''}; last by {last.get('by')} at "
                   f"{str(last.get('time'))[:16]}: added {'; '.join(added) or 'none'}, removed {'; '.join(removed) or 'none'}")
    return out


def age_text(ts, now) -> str:
    """The time since `ts` as a reader scans it: `under 1 min`, `7 min`, `2 h 5 min`, `3 d 4 h`."""
    when = _when(ts)
    if when is None:
        return "not established"
    minutes = max(0, int((now - when).total_seconds() // 60))
    if minutes < 1:
        return "under 1 min"
    if minutes < 60:
        return f"{minutes} min"
    hours, rest = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} h" + (f" {rest} min" if rest else "")
    days, hours = divmod(hours, 24)
    return f"{days} d" + (f" {hours} h" if hours else "")


def uncommitted_lines(files_by_card: dict, holders: dict, ordered: dict, ended) -> list:
    """One line for each card that has uncommitted files: the count, the holder (8 characters), the orderer and the first
    files. The files of a card whose holder session ended say so."""
    out = []
    for card, files in files_by_card.items():
        if not files:
            continue
        who = (holders.get(card) or "no holder")[:8]
        shown = ", ".join(files[:SHOWN]) + (f" and {len(files) - SHOWN} more" if len(files) > SHOWN else "")
        head = f"files of an ended session: {card}" if card in ended else f"uncommitted files of {card}"
        out.append(f"{head}: {len(files)} (held by {who}, ordered by {ordered.get(card) or 'owner'}): {shown}")
    return out


def no_done_lines(cards, rows) -> list:
    """`card X: no DONE file` for each (card, holder, time of the take) with no `result` row from the holder written since
    the take. A take time that can not be read counts every result row of the holder."""
    out = []
    for card, holder, taken in cards:
        since = _when(taken)
        done = False
        for row in rows or []:
            when = _when(row.get("ts")) if isinstance(row, dict) else None
            if (isinstance(row, dict) and row.get("kind") == "result" and row.get("from") == holder and when is not None
                    and (since is None or when >= since)):
                done = True
                break
        if not done:
            out.append(f"card {card}: no DONE file")
    return out


def agent_failed_lines(refusal_rows, agent_rows) -> list:
    """The failed agent record (R271c) as one line while no agent row was written after it."""
    failed = [r for r in refusal_rows or [] if isinstance(r, dict) and r.get("reason_id") == AGENT_FAILED
              and _when(r.get("time")) is not None]
    if not failed:
        return []
    last = max(failed, key=lambda r: _when(r["time"]))
    for row in agent_rows or []:
        stamps = [_when(row.get(k)) for k in ("started", "ended")] if isinstance(row, dict) else []
        if any(s is not None and s > _when(last["time"]) for s in stamps):
            return []
    return [f"agent record failed at {last['time']}: the agent result is not saved until an agent row is written again"]


# ---- the readers --------------------------------------------------------------------------------------------------------

def uncommitted_files(root) -> list:
    """The files git reports as changed or untracked, in git's order; [] when git can not be read. Git names a file from the
    top of the work tree (MW-140): a file under `root` is its root-relative path (a `str`); a file outside the root, or a name
    that cannot be placed, is a `helpers.Outside` carrying git's own name, never an in-root name of the same text."""
    import helpers
    import runner
    root = Path(root)
    try:
        proc = runner.git(root, "status", "--porcelain=v1", "-z", "-uall", "--no-renames", text=False)
        if proc.returncode != 0:
            return []
        prefix = helpers.top_prefix(root)
        out = []
        for entry in helpers.decode_git(proc.stdout).split("\0"):
            if len(entry) > 3:
                out.append(helpers.from_top(entry[3:], root, prefix))
        return out
    except Exception:
        return []


def outside_line(names) -> list:
    """MW-140: `outside the task root: <name>, ...` as one line for the uncommitted files outside the root (at most SHOWN
    named, the rest counted); no line for none. Such a file is never a card's file and never left out of the board."""
    names = list(dict.fromkeys(names))
    if not names:
        return []
    shown = ", ".join(names[:SHOWN]) + (f" and {len(names) - SHOWN} more" if len(names) > SHOWN else "")
    return [f"outside the task root: {shown}"]


def agent_and_failure_rows(state) -> tuple:
    import agents
    import logs
    import scorecard
    return (scorecard.read_rows(Path(state) / logs.REFUSALS), scorecard.read_rows(Path(state) / agents.AGENTS))


def failed_agent_lines(state) -> list:
    """The failed agent record line of a state folder (the start line and the board read it)."""
    try:
        return agent_failed_lines(*agent_and_failure_rows(state))
    except Exception:
        return []


def lines(root, profile, now=None) -> list:
    """The lines the board adds under `cards:` (no indent): old red, uncommitted files, no DONE file, the failed agent record."""
    import cardtool
    import helpers
    import leads
    import logs
    import profiles
    import records
    import register
    import scorecard
    root = Path(root)
    state, shared = profiles.state_dir(root, profile), profiles.shared_state_dir(root, profile)
    out = []
    try:
        out += old_red_lines(scorecard.read_rows(Path(state) / scorecard.COMMIT_TESTS))
    except Exception:
        pass
    try:
        reg = register.read(root, profile)
        held = records.holders(state, register.closed_ids(root, profile))
        open_rows = [r for r in reg if r.get("status") == "open" and held.get(r["id"])]
        ended = set(cardtool.stale_holders(root, profile, held, now=now))
        ordered = {r["id"]: r.get(register.ORDERED) or register.OWNER for r in open_rows}
        files = {r["id"]: [] for r in open_rows}
        outside = []
        if profile.get("vcs") == "git" and open_rows:
            for rel in uncommitted_files(root):
                if isinstance(rel, helpers.Outside):  # MW-140: git's own name, matched against no card
                    outside.append(rel.name)
                    continue
                for r in open_rows:
                    if any(helpers.matches(rel, e) for e in cardtool.paths_set(r.get("paths", ""))):
                        files[r["id"]].append(rel)
                        break
        out += uncommitted_lines(files, held, ordered, ended)
        out += outside_line(outside)
        rows = leads.all_rows(shared)
        out += no_done_lines([(r["id"], held[r["id"]], records.hold_time(state, r["id"], held[r["id"]]))
                              for r in open_rows], rows)
    except Exception:
        pass
    try:  # MW-137: the owner sees a re-record of a card's Paths here; nobody pings the owner
        live = {r["id"] for r in register.read(root, profile) if r.get("status") != "closed"}
        out += paths_lines(scorecard.read_rows(Path(state) / cardtool.PATHS_FILE), live)
    except Exception:
        pass
    out += failed_agent_lines(state)
    return out

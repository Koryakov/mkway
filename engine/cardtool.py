"""The cards tool (card MW-002, deliverable 6; card MW-003, deliverable 4).

Cards live in `<root>/<bundle.root>/cards/<PREFIX>-NNN-<slug>/CARD.md`, with the register `REGISTER.md` beside them
(the layout is fixed in the engine, D-8). The id is one past the highest number found in the register or in the
folder names, so an id never repeats (a row whose folder is gone still counts), and ids go past 999. Every register
write goes through `register.write`: the seal check, one writer at a time, write-to-temp then replace.

The one card form is the engine's: `cards/_TEMPLATE/CARD.md` of the engine copy this code runs from. It is never
read from the task's own `cards/` folder and never copied into it (decision C13): the form is part of the engine.
"""
from __future__ import annotations

import datetime
import json
import os
import posixpath
import re
import time
import types
from pathlib import Path
from typing import NamedTuple, Optional

import ledger
import logs
import outbox
import profiles
import records
import register
import runner

ENGINE_COPY = Path(__file__).resolve().parent.parent  # the copy (or the engine repository) this code belongs to


FORM_HINTS = {  # MW-112 (R284): the tool-validation ids say the correct form; a text that already names it is left as it is
    "card-unknown": ("register id", "; name a card by its register id (`mkway card list` shows them)"),
    "card-bad-move": ("allowed moves", "; `mkway card list` shows each card's status and the move the card form allows next"),
}


class CardError(Exception):
    def __init__(self, message: str, reason: str = "card-error"):
        known, hint = FORM_HINTS.get(reason, (None, ""))
        super().__init__(message + hint if hint and known not in message else message)
        self.reason = reason


def template_path() -> Path:
    return ENGINE_COPY / "cards" / "_TEMPLATE" / "CARD.md"


def cards_dir(root: Path, profile) -> Path:
    return Path(root) / profiles.bundle_root(profile) / "cards"


def prefix(profile) -> str:
    ids = profile.get("ids") if isinstance(profile, dict) else None
    value = ids.get("card_prefix") if isinstance(ids, dict) else None
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z][A-Z0-9]*", value):
        raise CardError("ids.card_prefix is not set in the profile (capital letters and digits, e.g. CARD)")
    return value


def id_pattern(profile):
    """The card id: the prefix, a dash and three or more digits, anchored at both ends of the id (defect 11)."""
    return re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(prefix(profile))}-[0-9]{{3,}}(?![0-9A-Za-z_])")


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40].strip("-") or "card"


def _highest(folder: Path, rows: list, card_prefix: str) -> int:
    pattern = re.compile(rf"^{re.escape(card_prefix)}-(\d+)(?:-|$)")
    numbers = [int(m.group(1)) for row in rows if (m := pattern.match(row.get("id", "")))]
    if folder.is_dir():
        numbers += [int(m.group(1)) for p in folder.iterdir() if p.is_dir() and (m := pattern.match(p.name))]
    return max(numbers, default=0)


def new_card(root: Path, profile, title: str) -> Path:
    """Write a new card from the engine's form and add its register row (`proposed`); return the card folder."""
    card_prefix = prefix(profile)
    title = " ".join(title.split()).replace("|", "/")
    if not title:
        raise CardError("the card needs a title")
    folder = cards_dir(root, profile)
    made = {}

    def mutate(rows):
        card_id = f"{card_prefix}-{_highest(folder, rows, card_prefix) + 1:03d}"
        card_folder = folder / f"{card_id}-{slug(title)}"
        lines = template_path().read_text(encoding="utf-8").splitlines(keepends=True)
        lines[0] = f"# {card_id}: {title}\n"
        card_folder.mkdir(parents=True)
        with open(card_folder / "CARD.md", "w", encoding="utf-8", newline="\n") as fh:
            fh.write("".join(lines))
        made["folder"] = card_folder
        rel = card_folder.relative_to(Path(root)).as_posix()
        return rows + [{"id": card_id, "title": title, "status": "proposed", "paths": "", "folder": f"`{rel}`",
                        register.ORDERED: register.OWNER}]

    register.write(root, profile, mutate)
    return made["folder"]


def list_cards(root: Path, profile) -> list:
    return [[r["id"], r["title"], r["status"], r["paths"], r["folder"]] for r in register.read(root, profile)]


# --- card moves (card MW-003, deliverable 4; R15 A1-A3, R19c, v3.1) -------------------------------------------------

DEFAULT_OWNER_MOVES = ["open", "closed"]
DEFAULT_TEST_ROOTS = ["tests"]
SET_TARGETS = ("open", "waiting", "closed")  # `card set` never writes `proposed` or `waiting-owner` itself
READING = "checked by reading"


def owner_moves(profile) -> list:
    cards = profile.get("cards") if isinstance(profile, dict) else None
    moves = cards.get("owner_moves") if isinstance(cards, dict) else None
    return list(moves) if isinstance(moves, list) else list(DEFAULT_OWNER_MOVES)


def norm_entry(entry: str) -> str:
    """One Paths entry, normalised: backticks and spaces off, `\\` to `/`, leading `./` and `/` off, trailing `/`
    off; `.` alone is empty."""
    e = entry.strip().strip("`").strip().replace("\\", "/")
    while e.startswith("./"):
        e = e[2:]
    e = e.lstrip("/").rstrip("/")
    return "" if e == "." else e


def test_roots(profile) -> list:
    value = profile.get("test_roots") if isinstance(profile, dict) else None
    roots = value if isinstance(value, list) and value else DEFAULT_TEST_ROOTS
    return [r for r in (norm_entry(x) for x in roots if isinstance(x, str)) if r]


test_roots.__test__ = False  # not a pytest test, though its name starts with `test`


def card_file(root: Path, profile, card_id: str) -> Path:
    row = register.find(register.read(root, profile), card_id)
    if row is None:
        raise CardError(f"{card_id} is not in the register", reason="card-unknown")
    return Path(root) / row.get("folder", "").strip().strip("`") / "CARD.md"


def header(text: str, label: str) -> str:
    m = re.search(rf"^\| \*\*{re.escape(label)}\*\* \|(.*)\|\s*$", text, flags=re.M)
    return m.group(1).strip() if m else ""


def paths_set(cell: str) -> frozenset:
    """The set the subtask gate compares: entries normalised; order, blanks and spaces ignored."""
    return frozenset(e for e in (norm_entry(x) for x in re.split(r"[,;]", cell or "")) if e)


def card_paths(root: Path, profile, card_id: str) -> str:
    return header(card_file(root, profile, card_id).read_text(encoding="utf-8"), "Paths")


EVERY_PATH_PROBES = ("a", "a.py", ".h", "Z9", "ab/c.py", "d/e/f/g.txt", "x y/z")


def _too_wide(entry: str, roots: list) -> bool:
    """Empty, a glob that matches every path (probed with `helpers.matches`, so the question-mark forms count too),
    or a test root with or without a trailing `/**` (v3.1; close check H2)."""
    import helpers
    if not entry:
        return True
    if all(helpers.matches(p, entry) for p in EVERY_PATH_PROBES):
        return True
    parts = entry.split("/")
    if all(p in ("*", "**") for p in parts) and (len(parts) == 1 or "**" in parts):
        return True
    base = entry
    while base.endswith("/**"):
        base = base[:-3]
    return base in roots


def paths_entries(cell: str) -> list:
    """The entries of a Paths cell, or of the values a `card paths` call names, as written (blank ones left out)."""
    return [x for x in re.split(r"[,;]", cell or "") if x.strip().strip("`").strip()]


def wide_entries(raw: list, profile) -> list:
    """The entries of `raw` (as written) that are too wide: the one check of the first open and of a re-record (MW-137)."""
    roots = test_roots(profile)
    return [x.strip() for x in raw if _too_wide(norm_entry(x), roots)]


def wide_error(card_id: str, wide: list) -> "CardError":
    return CardError(f"{card_id}: Paths entry {', '.join(wide)} names the whole repository or a test root; name "
                     f"the files and folders the card edits", reason="card-paths-too-wide")


def recorded_paths(root: Path, profile, card_id: str) -> str:
    """The card's Paths as the register records them at `card open`; `card-paths-too-wide` refuses."""
    raw = paths_entries(card_paths(root, profile, card_id))
    wide = wide_entries(raw, profile)
    if wide:
        raise wide_error(card_id, wide)
    return "; ".join(dict.fromkeys(norm_entry(x) for x in raw))


def _test_cells(text: str) -> list:
    """The Test cells of the Acceptance examples table."""
    part = text.split("## Acceptance examples", 1)
    if len(part) < 2:
        return []
    cells, index = [], None
    for line in part[1].splitlines():
        if line.startswith("## "):
            break
        if not line.startswith("|"):
            if index is not None:
                break
            continue
        row = [c.strip() for c in line.strip().strip("|").split("|")]
        if index is None:
            index = row.index("Test") if "Test" in row else len(row) - 1
            continue
        if set(line) <= set("|-: "):
            continue
        cells.append(row[index] if index < len(row) else "")
    return cells


CELL_FORM = "a `; ` list of full node ids (`tests/test_x.py::test_y`), or `checked by reading: <path>`"


def close_problem(root: Path, profile, card_id: str):
    """None when every Acceptance row's Test cell has the one form (list item 14, R45 points 5 and 6): a `; ` list of
    full node ids that exist under `test_roots` (`[...]` ignored), or `checked by reading: <path>` naming a file that
    exists, on any card; else the first problem, which says how to write the cell."""
    text = card_file(root, profile, card_id).read_text(encoding="utf-8")
    roots = test_roots(profile)
    cells = _test_cells(text)
    if not cells:
        return "the Acceptance examples table has no rows"
    for n, cell in enumerate(cells, 1):
        value = cell.replace("`", "").strip()
        if value.startswith(READING):
            path = value[len(READING):].strip()
            if not path.startswith(":") or not path[1:].strip():
                return f"row {n}: a bare `{READING}` is a form fault: name the file you read " \
                       f"(`{READING}: <path>`)"
            rel = posixpath.normpath(norm_entry(path[1:].strip()) or ".")
            if rel.startswith("..") or not (Path(root) / rel).is_file():
                return f"row {n}: {rel} does not exist; `{READING}: <path>` names a file in the repository"
            continue
        if "," in value:
            return f"row {n}: a `,` list is a form fault: use {CELL_FORM}"
        items = [x.strip() for x in value.split(";") if x.strip()]
        if not items:
            return f"row {n}: the Test cell is empty"
        for item in items:
            if item.startswith("::") or "::" not in item:
                return f"row {n}: `{item}` is not a full node id: use {CELL_FORM}"
            file, _, name = item.partition("::")
            file = posixpath.normpath(norm_entry(file) or ".")  # `..` resolved first (close check L3)
            name = re.sub(r"\[.*\]$", "", name).strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                return f"row {n}: `{item}` names no test function"
            if not any(file == r or file.startswith(r + "/") for r in roots):
                return f"row {n}: {file} is not under the test roots ({', '.join(roots)})"
            try:
                source = (Path(root) / file).read_text(encoding="utf-8")
            except OSError:
                return f"row {n}: {file} does not exist"
            if not re.search(rf"^\s*(?:async\s+)?def {re.escape(name)}\(", source, flags=re.M):
                return f"row {n}: {file} holds no `def {name}(`"
    return None


# --- who ordered a card (card MW-011, rules 1 to 3) ------------------------------------------------------------------

NE = "not established"


def unchecked_outbox(root: Path, profile, card_id: str, text: str) -> None:
    """MW-019: refuse `close-unchecked-outbox` while an Acceptance row names a file under `outbox.dir` whose check is not
    valid (the owner's close and the orderer's close both come here)."""
    problem = outbox.close_problem(root, profile, card_id, text)
    if problem:
        raise CardError(problem, reason="close-unchecked-outbox")


def unbuilt_deliverables(root: Path, profile, card_id: str, text: str) -> None:
    """MW-020: refuse `close-deliverable-unbuilt` while an Acceptance row names a deliverable that was not built from its
    current text, then `base-unknown` for a path that needs a delivered base and has none (the owner's close and the
    orderer's close both come here)."""
    import deliverables
    problem = deliverables.close_problem(root, profile, card_id, text)
    if problem:
        raise CardError(problem[1], reason=problem[0])


def verdicts_required(profile) -> bool:
    """`cards.verdicts` (MW-068): on unless the profile says `off`; a fresh install's profile never says it."""
    cards = profile.get("cards") if isinstance(profile, dict) else None
    return not (isinstance(cards, dict) and cards.get("verdicts") == "off")


def unverdicted_tests(root: Path, profile, card_id: str, text: str) -> None:
    """MW-068: refuse `verdict-missing`, `verdict-by-author`, `verdict-by-holder`, `verdict-weak` or `verdict-wrong` while a test node an
    Acceptance row names has no good verdict row by a reader who did not write the test (`tests/verdicts/<card>.md`);
    `cards.verdicts: off` skips it, a card that names no node is not affected (the owner's close and the orderer's
    close both come here)."""
    if not verdicts_required(profile):
        return
    import verdicts
    state = profiles.state_dir(Path(root), profile)
    holder = records.holders(state, register.closed_ids(root, profile)).get(card_id, "")
    nodes, checkers = test_nodes(text), profiles.outbox_settings(profile)["checkers"]
    problem = verdicts.problem(root, card_id, nodes, holder, state, checkers, text)
    if problem:
        raise CardError(problem[1], reason=problem[0])
    note = verdicts.warning(nodes, checkers)
    if note:  # ruling R179: no checker named, so the close passes unenforced and says so
        verdicts.record_not_enforced(root, profile, card_id)
        NOTES.append(note)


NOTES: list = []  # lines a close adds to its output (the CLI prints them after the result line)


def take_notes() -> list:
    """The notes the last close left (MW-068, ruling R179), and clear them."""
    out = list(NOTES)
    NOTES.clear()
    return out


def approver(profile) -> str:
    """`orderer` or `owner-only` (the default): who makes a session's `card close` pass (`cards.approver`)."""
    cards = profile.get("cards") if isinstance(profile, dict) else None
    return "orderer" if isinstance(cards, dict) and cards.get("approver") == "orderer" else "owner-only"


def stale_holders(root: Path, profile, held: dict, now=None) -> dict:
    """MW-045: card id -> holder, for the holders in `held` (`records.holders`) that are stale: the last row of the
    session in `sessions.jsonl` is older than `cards.stale_hours`; with no row, its take record is older than that.
    An unreadable time is never stale (the strict reading: a live builder is never freed on a guess)."""
    import records
    import sessions
    state, shared = profiles.state_dir(root, profile), profiles.shared_state_dir(root, profile)
    limit = datetime.timedelta(hours=profiles.cards_stale_hours(profile))
    now = now or logs.now()
    seen = sessions.latest(shared)
    out = {}
    for card, who in held.items():
        text = seen[who][0] if who in seen else records.hold_time(state, card, who)
        when = sessions._when(text)
        if when is not None and now - when > limit:
            out[card] = who
    return out


def seen_sessions(state, shared=None) -> tuple:
    """({session id: last-seen time or ""}, rows with no session id): every session id in the shell records and the
    agent records (a search is a shell record), and with `shared` (the shared state folder, MW-017) every session of
    its `sessions.jsonl`. A record without an id (the payload did not give one) is counted,
    never listed; the owner's own records carry no session and count nowhere."""
    import agents
    import records
    import sessions
    seen: dict = {}
    missing = 0

    def note(sid, moments):
        nonlocal missing
        if not isinstance(sid, str) or not sid.strip() or sid == NE:
            missing += 1
            return
        stamps = [m for m in moments if isinstance(m, str) and m and m != NE]
        seen[sid] = max([seen.get(sid, ""), *stamps])

    for row in records.rows(state):
        if row.get("by") != "owner":
            note(row.get("session_id"), [row.get("time")])
    for row in agents.rows(state):
        note(row.get("session_id"), [row.get("started"), row.get("ended")])
    if shared is not None:
        for sid, (stamp, _root) in sessions.latest(shared).items():
            seen[sid] = max(seen.get(sid, ""), stamp)
    return seen, missing


def card_ref(profile, text: str) -> str:
    """A card id as typed: a bare number (`11`, `011`) takes the profile's card prefix."""
    text = (text or "").strip()
    return f"{prefix(profile)}-{int(text):03d}" if re.fullmatch(r"[0-9]+", text) else text


def resolve_session(state, who: str, shared=None) -> str:
    """`owner`, or the one session id seen in the state records (and the shared sessions file) that `who` names (the
    whole id, else a prefix that matches exactly one); `give-unknown` or `give-ambiguous` (with the candidates)
    otherwise."""
    if who == register.OWNER:
        return who
    ids = sorted(seen_sessions(state, shared)[0])
    if who and who in ids:
        return who
    found = [i for i in ids if who and i.startswith(who)]
    if len(found) == 1:
        return found[0]
    if not found:
        raise CardError(f"no session id seen in the state records starts with {who!r}; `mkway sessions` lists them",
                        reason="give-unknown")
    raise CardError(f"{who!r} starts {len(found)} session ids: {', '.join(found)}; give more of the id",
                    reason="give-ambiguous")


def give(root: Path, profile, state, card: str, who: str) -> tuple:
    """The owner's `give`: set `Ordered by` of one card; (card id, value written)."""
    card_id = card_ref(profile, card)
    if register.find(register.read(root, profile), card_id) is None:
        raise CardError(f"{card_id} is not in the register", reason="card-unknown")
    value = resolve_session(state, who, profiles.shared_state_dir(root, profile))
    if register.file_has_orderer(root, profile) is not True:
        raise CardError(f"the register has no `{register.orderer_column(profile)}` column; the owner adds it with "
                        f"`mkway card resync --add-ordered-by` in their own terminal", reason="give-no-column")
    register.set_ordered(root, profile, card_id, value)
    return card_id, value


# --- the close by the orderer (card MW-011, rules 4 and 5) -----------------------------------------------------------
# Only the hook input knows a session's id. The lock gate checks the orderer and the holder before the command runs
# and leaves a one-use permit that names the session; the CLI reads it, checks again with that id, runs the tests the
# Acceptance rows name, and closes. A permit is never read from the command line.

PERMITS = "permits"
PERMIT_SECONDS = 120
CLOSE_TEST_SECONDS = 600
TEST_ENV = ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE",
            "LANG", "LC_ALL", "ENGINE_TERMS_FILE")
OWNER_TERMINAL = "the owner closes it in their own terminal"


def _permit_file(state, card_id: str, kind: str = "close") -> Optional[Path]:
    if not isinstance(card_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", card_id):
        return None
    return Path(state) / PERMITS / f"{kind}-{card_id}.json"


def issue_close_permit(state, card_id: str, session, kind: str = "close") -> bool:
    """Leave the one-use permit of a close (MW-028: `kind` "open" for a lead's open of a card it ordered): the card
    and the session id the hook input gave."""
    target = _permit_file(state, card_id, kind)
    if target is None or not isinstance(session, str) or not session.strip():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps({"card": card_id, "session_id": session,
                               "time": logs.now().isoformat(timespec="milliseconds")}), encoding="utf-8")
    os.replace(tmp, target)
    return True


def take_close_permit(state, card_id: str, kind: str = "close") -> Optional[str]:
    """The session id of the card's permit of that kind, once: the file is removed whatever it holds. None when there
    is none, it is older than PERMIT_SECONDS, or it cannot be read."""
    target = _permit_file(state, card_id, kind)
    if target is None:
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        os.remove(target)
        moment = datetime.datetime.fromisoformat(data["time"])
        moment = moment if moment.tzinfo else moment.replace(tzinfo=datetime.timezone.utc)
        age = (logs.now() - moment).total_seconds()
        session = data.get("session_id")
        if data.get("card") == card_id and isinstance(session, str) and session and -5 <= age <= PERMIT_SECONDS:
            return session
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass
    return None


BY_PERMIT = "by.json"  # MW-015: the permit of a `ledger add` or `ask default`, which names no card


def issue_by_permit(state, session) -> bool:
    """Leave the one-use permit that names the session of a `ledger add` or `ask default` call (MW-015)."""
    if not isinstance(session, str) or not session.strip():
        return False
    target = Path(state) / PERMITS / BY_PERMIT
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps({"session_id": session, "time": logs.now().isoformat(timespec="milliseconds")}),
                   encoding="utf-8")
    os.replace(tmp, target)
    return True


def take_by_permit(state) -> Optional[str]:
    """The session id of the by-permit, once: the file is removed whatever it holds. None when there is none, it is
    older than PERMIT_SECONDS, or it cannot be read."""
    target = Path(state) / PERMITS / BY_PERMIT
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        os.remove(target)
        moment = datetime.datetime.fromisoformat(data["time"])
        moment = moment if moment.tzinfo else moment.replace(tzinfo=datetime.timezone.utc)
        age = (logs.now() - moment).total_seconds()
        session = data.get("session_id")
        if isinstance(session, str) and session and -5 <= age <= PERMIT_SECONDS:
            return session
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass
    return None


def orderer_problem(row: dict, holders: dict, session):
    """None when `session` may close the card of `row` as its orderer, else (reason id, message that names the way
    out): `close-not-orderer` (no id in the hook input, ordered by the owner, ordered by another session) or
    `close-by-holder`. `holders` is `records.holders`."""
    card_id = row.get("id", "")
    ordered = row.get(register.ORDERED) or register.OWNER
    give = f"the owner gives the order to a session with `mkway give {card_id} <session id prefix>`"
    if not isinstance(session, str) or not session.strip():
        return ("close-not-orderer", f"{card_id}: the hook input names no session id for this call (not established), "
                                     f"so the orderer cannot be established; run it again in the session that "
                                     f"ordered the card, or {OWNER_TERMINAL}")
    if ordered == register.OWNER:
        return ("close-not-orderer", f"{card_id} was ordered by the owner: {OWNER_TERMINAL}, or {give}")
    if ordered != session:
        return ("close-not-orderer", f"{card_id} was ordered by {ordered}, not by this session: only that session "
                                     f"closes it, or {OWNER_TERMINAL}")
    if holders.get(card_id) == session:
        return ("close-by-holder", f"{card_id} is held by this session, which also ordered it: a session never "
                                   f"approves its own work. {give[0].upper() + give[1:]}, or {OWNER_TERMINAL}")
    return None


def test_nodes(text: str) -> list:
    """The node ids the Acceptance rows name, in order, once each; a `checked by reading` row names none."""
    nodes = []
    for cell in _test_cells(text):
        value = cell.replace("`", "").strip()
        if value.startswith(READING):
            continue
        for item in (x.strip() for x in value.split(";")):
            if "::" in item:
                file, _, name = item.partition("::")
                nodes.append(f"{norm_entry(file)}::{name}")
    return list(dict.fromkeys(nodes))


test_nodes.__test__ = False  # not a pytest test, though its name starts with `test`


ON_HEAD = " (the tests ran on HEAD's tree: a file that is only staged, modified or untracked is not seen; commit it)"


def tests_problem(root: Path, profile, nodes: list) -> Optional[str]:
    """None when `python -m pytest <nodes>` passes; else why not (the red ids, or the tail). MW-070: with vcs git the
    nodes run in an export of HEAD's tree, the one the commit gate makes (MW-060), so nothing staged, unstaged or
    untracked is seen; with vcs none there is no HEAD and they run in the root."""
    if not nodes:
        return None
    if profiles.vcs(profile) != "git":
        return _nodes_problem(root, profile, nodes, "")
    import gate_commit_tests as export
    import helpers
    state = profiles.state_dir(root, profile)
    work = Path(state) / export.FOLDER / f"close-{os.getpid()}-{int(time.time() * 1000)}"
    try:
        try:
            if export._git(root, "rev-parse", "--verify", "-q", "HEAD").returncode != 0:
                return "HEAD has no commit, so there is no tree of HEAD to run the tests on: commit the work first"
            top = Path(export._read(root, "rev-parse", "--show-toplevel").strip())
            # `_head_folder` reads only these four fields of the gate's run object
            run = types.SimpleNamespace(work=work, folder=Path(root), top=top, prefix=helpers.top_prefix(root))
            folder = export._head_folder(run)
        except (export.NotRun, OSError, ValueError, runner.Refused, runner.TimeoutExpired) as exc:
            return f"the tree of HEAD could not be exported ({exc.__class__.__name__}: {exc}), so the tests did not run"
        if not folder.is_dir():
            return "HEAD's tree holds no folder of this task root, so the tests did not run: commit the work first"
        return _nodes_problem(folder, profile, nodes, ON_HEAD)
    finally:
        export._remove(work, state)


def _nodes_problem(folder: Path, profile, nodes: list, note: str) -> Optional[str]:
    """None when the nodes pass in `folder`; else why not, with `note` at the end of the text."""
    root = folder
    py = (profile.get("python") or {}).get("command") if isinstance(profile.get("python"), dict) else None
    py = py if isinstance(py, str) and py else "python"
    env = {k: os.environ[k] for k in (*TEST_ENV, *profiles.test_env(profile)) if k in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    try:
        code, out, err = runner.run_tree([py, "-m", "pytest", "-q", "-p", "no:cacheprovider", *nodes],
                                         timeout=CLOSE_TEST_SECONDS, python=py, cwd=str(root), env=env)
    except (runner.Refused, OSError) as exc:
        return f"the tests could not be started ({exc.__class__.__name__}: {exc})"
    if code is None:
        return f"the tests did not finish within {CLOSE_TEST_SECONDS} s{note}"
    if code == 0:
        return None
    text = (out or b"").decode("utf-8", "replace") + "\n" + (err or b"").decode("utf-8", "replace")
    import gate_commit_tests as export  # late: it imports this module (MW-114: one reader of ids, whole)
    failing = [f.replace("\\", "/") for f in export.failed_ids(text)]  # the card's form of a node id
    if failing:
        return f"{len(failing)} failing: " + "; ".join(failing[:10]) + note
    tail = [ln.strip() for ln in text.splitlines() if ln.strip()][-3:]
    return f"the run exited {code} and named no failing test ({' | '.join(tail)[:300]}){note}"


# --- the red a card inherits at its take (card MW-108, concept lines 2 and 5, kind K2; rulings R270a, R283) -----------------

INHERITED_FILE = "inherited_red.jsonl"  # `<state.dir>/`: one row per `card take` and per `card release-red`, written by the engine
MAX_SHOWN = 5


class Inherited(NamedTuple):
    """The red one card inherited, read from the rows of INHERITED_FILE. `taken`: the card has a take row (a card taken
    before the record existed has none, and keeps the rules it had). `established`: a take row of the card was
    established. `red`: ids recorded red at its take (and released to it), minus the ids released away. `green`: ids its
    take recorded green. `released`: {id: card it was released to} for the ids released away."""
    taken: bool
    established: bool
    red: frozenset
    green: frozenset
    released: dict


def inherited_from_rows(rows, card_id: str) -> Inherited:
    """Pure: the inherited red of `card_id` from the rows in the order they were written. A take row that is established
    adds its red and green ids, minus what was released away before; one that is not established adds none. A
    `release-red` row moves its id: away from its `card`, to its `to` card; a later take never brings it back."""
    taken = established = False
    red, green, released = set(), set(), {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("kind") == "take" and row.get("card") == card_id:
            taken = True
            if row.get("established") is True:
                established = True
                red |= {i for i in row.get("red") or [] if i not in released}
                green |= set(row.get("green") or [])
        elif row.get("kind") == "release-red":
            test = row.get("test")
            if row.get("card") == card_id:
                red.discard(test)
                released[test] = row.get("to")
            elif row.get("to") == card_id:
                red.add(test)
                released.pop(test, None)
    return Inherited(taken, established, frozenset(red), frozenset(green), released)


def inherited_rows(state) -> list:
    """The rows of INHERITED_FILE in order; none when the file is missing or cannot be read, a line that is not JSON is skipped."""
    path = Path(state) / INHERITED_FILE
    rows = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    except OSError:
        return []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def inherited_of(state, card_id: str) -> Inherited:
    return inherited_from_rows(inherited_rows(state), card_id)


def record_inherited_red(root: Path, profile, card_id: str) -> str:
    """`card take`: write the take row of the card and return the line the take prints. The red at HEAD inside the card's
    Paths comes from `gate_commit_tests.head_red`, the rows the commit gate kept; the suite is never run here. A take that
    cannot be established says so in its row and in the line, never silence (R283 1): every red in the card's Paths then
    counts as new for this card, at its commits and at its close. A row that cannot be written raises OSError."""
    import gate_commit_tests as gate  # late: it imports this module
    row = register.find(register.read(root, profile), card_id) or {}
    found = gate.head_red(root, profile, paths_set(row.get("paths", "")))
    logs.append_jsonl(profiles.state_dir(Path(root), profile) / INHERITED_FILE, {
        "time": logs.now().isoformat(timespec="milliseconds"), "kind": "take", "card": card_id,
        "established": found.established, "red": found.red, "green": found.green, "record": found.record,
        "behind": found.behind})
    if not found.established:
        return (f"inherited red: {NE} (no usable test record of HEAD's history), so every red in the Paths of {card_id} "
                f"counts as new red for this card; after a refused commit, or any run that keeps a test row of "
                f"HEAD, release the card and take it again (`mkway card release {card_id}` then `mkway card take "
                f"{card_id}`): the new take records those reds")
    shown = "; ".join(found.red[:MAX_SHOWN]) + (f"; and {len(found.red) - MAX_SHOWN} more" if len(found.red) > MAX_SHOWN else "")
    return f"inherited red: {len(found.red)} recorded for {card_id}" + (f": {shown}" if found.red else "")


def release_red(root: Path, profile, state, test_id: str, to_card: str, caller: Optional[str]) -> str:
    """`card release-red <test id> --to <card>` (R283 4): the card's orderer moves one inherited red id to another named
    open card, and the close of that card then needs it green. `caller` is the session id of the by-permit, None for the
    owner's terminal (who orders the cards that name no session). One row in INHERITED_FILE: the cards, the test id and the
    orderer. Refusals: `card-unknown` (no such card), `card-bad-move` (the target is not open, no open card inherited the
    id, two cards did, or the id is already the target's), `close-not-orderer` (the caller did not order the card that holds
    the id)."""
    rows = register.read(root, profile)
    target = register.find(rows, to_card)
    if target is None:
        raise CardError(f"{to_card} is not in the register", reason="card-unknown")
    if target.get("status") != "open":
        raise CardError(f"{to_card} is {target.get('status')}: a red is released only to an open card, which then owns "
                        f"it; name an open card with --to", reason="card-bad-move")
    holders = [r["id"] for r in rows if r.get("status") != "closed" and test_id in inherited_of(state, r["id"]).red]
    if not holders:
        raise CardError(f"{test_id} is no inherited red of an open card (its take recorded it red, it was not released "
                        f"away): nothing to release", reason="card-bad-move")
    if len(holders) > 1 or holders[0] == to_card:
        raise CardError(f"{test_id} is inherited by {', '.join(holders)}: it is released from one card to a different "
                        f"one; the owner settles two holders", reason="card-bad-move")
    source = register.find(rows, holders[0])
    ordered = source.get(register.ORDERED) or register.OWNER
    who = caller or register.OWNER
    if who != ordered:
        raise CardError(f"{holders[0]} was ordered by {ordered}, not by {who}: only its orderer releases a red of it; the "
                        f"owner gives the order with `mkway give {holders[0]} <session id prefix>`", reason="close-not-orderer")
    logs.append_jsonl(Path(state) / INHERITED_FILE, {
        "time": logs.now().isoformat(timespec="milliseconds"), "kind": "release-red", "card": holders[0], "to": to_card,
        "test": test_id, "by": who, "session": who})
    try:
        append_log_row(root, profile, holders[0], "release-red", f"{test_id} released to {to_card} by {who[:8]}")
    except (OSError, CardError):
        pass  # the record row is the proof; the Log line is a courtesy
    return f"{test_id} released from {holders[0]} to {to_card}"


def _paths_test_files(root: Path, profile, card_id: str) -> list:
    """The entries of the card's Paths that are test files or folders under the test roots and exist (no glob)."""
    row = register.find(register.read(root, profile), card_id) or {}
    roots = test_roots(profile)
    return sorted(e for e in paths_set(row.get("paths", ""))
                  if not any(c in e for c in "*?[") and any(e == r or e.startswith(r + "/") for r in roots)
                  and (Path(root) / e).exists())


def close_nodes(root: Path, profile, card_id: str, text: str) -> tuple:
    """(the nodes the orderer's close runs, whether some came from the inherited red). The Acceptance rows' nodes, the ids
    the card inherited, and (R283 1) when its take was not established the test files of its Paths, so any red in them
    refuses."""
    inherited = inherited_of(profiles.state_dir(Path(root), profile), card_id)
    extra = sorted(inherited.red)
    if inherited.taken and not inherited.established:
        extra += _paths_test_files(root, profile, card_id)
    return list(dict.fromkeys([*test_nodes(text), *extra])), bool(extra)


def append_log_row(root: Path, profile, card_id: str, step: str, result: str) -> None:
    """One row at the end of the card's Log table, in the file's own line ends."""
    target = card_file(root, profile, card_id)
    raw = target.read_bytes().decode("utf-8")
    eol = "\r\n" if "\r\n" in raw else "\n"
    if "## 8. Log" not in raw:
        raw = raw.rstrip("\r\n") + f"{eol}{eol}## 8. Log{eol}{eol}| Date | Step | Commit | Result |{eol}|---|---|---|---|"
    row = f"| {logs.now().date().isoformat()} | {step} | - | {result.replace('|', '/')} |"
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_bytes((raw.rstrip("\r\n") + eol + row + eol).encode("utf-8"))
    os.replace(tmp, target)


def allowed_moves(status: str, session: bool) -> list:
    """The moves the chain allows from a status (R15 A1, R19c): a session sets `waiting` only from `open` and never
    lifts the owner's pause (`waiting-owner`)."""
    return {
        "proposed": ["open", "closed"],
        "open": ["open", "waiting", "closed"],
        "waiting": ["open", "closed"] if session else ["open", "waiting", "closed"],
        "waiting-owner": ["closed"] if session else ["open", "closed"],
        "closed": ["open"],
    }.get(status, [])


def open_problem(row: dict, session, is_lead: bool):
    """MW-028: None when `session` may open the card of `row` as its orderer, else (reason id, message that names the
    way out). Only a registered lead, only a card it ordered, only while the card is `proposed`; a card the owner
    ordered, or another session ordered, stays the owner's to open."""
    card_id = row.get("id", "")
    ordered = row.get(register.ORDERED) or register.OWNER
    if not isinstance(session, str) or not session.strip() or not is_lead or ordered != session:
        return ("owner-only-command", f"`mkway card open` is the owner's command for {card_id}: only a registered lead "
                                      f"opens a card it ordered; otherwise the owner opens it in their own terminal, "
                                      f"where no hook runs")
    if row.get("status") != "proposed":
        return ("card-bad-move", f"{card_id} is {row.get('status')}; a lead opens only a proposed card it ordered")
    return None


# --- the lead re-records the Paths of an open card it ordered (card MW-137; rulings R352 A, R353) --------------------------
# Paths are recorded once, at the first open from `proposed` (H1, R54). When a decision legitimately widens (or narrows) a
# card, the lead role that ordered it re-records them with `card paths <id> --add ... --remove ...`. The lead's intent is in
# the CALL; the card file is written by the holder after the open, so it is never the source: the engine records only when
# the file's Paths equal the recorded set plus and minus the named entries (R353 h). The checks of the first open run here
# through the same code (`wide_entries`, `recorded_paths`). The owner's terminal may run it too.

PATHS_FILE = "paths_changes.jsonl"  # `<state.dir>/`: one row per re-record: time, card, old set, new set, who


def _show(items) -> str:
    return "; ".join(sorted(items)) or "none"


def paths_state_problem(row: dict):
    """None when the card of `row` is in a state a re-record fits: `open`, or `waiting` (the holder's own pause). Else
    (`paths-card-state`, text that names the move that fits): `proposed`, `closed`, `waiting-owner` (the owner's pause)."""
    card_id, status = row.get("id", ""), row.get("status", "")
    if status in ("open", "waiting"):
        return None
    if status == "proposed":
        return ("paths-card-state", f"{card_id} is proposed: its Paths are recorded when it is opened, so there is nothing "
                                    f"to re-record yet. Open it with `mkway card open {card_id}` (the lead that ordered it "
                                    f"runs it; otherwise the owner, in their own terminal), then repeat this call if the "
                                    f"card file's Paths still differ")
    if status == "waiting-owner":
        return ("paths-card-state", f"{card_id} is paused by the owner (waiting-owner): the owner lifts the pause with "
                                    f"`mkway card open {card_id}` in their own terminal, then the lead repeats this call")
    return ("paths-card-state", f"{card_id} is {status}: the owner re-opens it with `mkway card open {card_id}` in their own "
                                f"terminal (a re-open keeps the recorded Paths), then the lead repeats this call")


def paths_problem(row: dict, session, is_lead: bool, holder):
    """None when `session` may re-record the Paths of the card of `row`, else (reason id, text that names the way out).
    The same rule as the lead's open and close (R356): the caller is a registered lead AND the card's `Ordered by` is the
    caller's own session id; a card another session ordered is refused, also when that session is or was a lead. In this
    order: `paths-not-lead` (no registered lead now), `paths-by-holder` (the holder never changes the Paths of its own card,
    also when it is a lead), `paths-not-orderer` (the card was ordered by the owner, or by another session), then the state
    (`paths_state_problem`). A planned change of lead is the existing hand-off: `give` and `lead accept` set `Ordered by` to
    the new lead. `holder`: the card's holder, or None."""
    card_id = row.get("id", "")
    ordered = row.get(register.ORDERED) or register.OWNER
    if not isinstance(session, str) or not session.strip() or not is_lead:
        return ("paths-not-lead", f"{card_id}: `mkway card paths` is the lead's command: only a registered lead that "
                                  f"ordered the card re-records its Paths, and this session is none. The lead that ordered "
                                  f"it runs it (send it the entry with `mkway send`), or the owner runs it in their own "
                                  f"terminal")
    if holder == session:
        return ("paths-by-holder", f"{card_id} is held by this session: a holder never changes the Paths of its own card, "
                                   f"also when it is a lead. The lead that ordered it ({ordered}) runs `mkway card paths "
                                   f"{card_id} --add <entry>` (a lead that also holds it first hands the card to another "
                                   f"lead: `mkway give {card_id} <id prefix>`, then that lead runs `mkway lead accept "
                                   f"{card_id}`), or the owner runs it in their own terminal")
    if ordered == register.OWNER:
        return ("paths-not-orderer", f"{card_id} was ordered by the owner, not by a lead: its Paths stay the owner's. The "
                                     f"owner changes the Paths cell of its row in the register and runs `python "
                                     f"mkway/engine/mkway.py card resync` in their own terminal")
    if ordered != session:
        return ("paths-not-orderer", f"{card_id} was ordered by {ordered}, not by this session: only the session that ordered "
                                     f"a card re-records its Paths, also when another session is or was a lead. Hand the "
                                     f"order over: {ordered} runs `mkway give {card_id} <your id prefix>` and this session "
                                     f"runs `mkway lead accept {card_id}`; or the owner runs `mkway give {card_id} <id "
                                     f"prefix>` (it needs no accept) in their own terminal")
    return paths_state_problem(row)


def paths_problem_for(root: Path, profile, row: dict, session):
    """`paths_problem` with its facts read: the leads file and the records (the lock gate and the command both come here)."""
    import leads  # leads imports this module
    state, shared = profiles.state_dir(Path(root), profile), profiles.shared_state_dir(Path(root), profile)
    holder = records.holders(state, register.closed_ids(root, profile)).get(row.get("id", ""))
    return paths_problem(row, session, leads.is_lead(shared, session), holder)


class PathsChange(NamedTuple):
    """What a re-record did: the card, the old and the new set (sorted), who, the holder at that moment, the notice row
    written to it (None: no holder, or it could not be written, see `note`) and a line for what could not be written."""
    card: str
    old: tuple
    new: tuple
    by: str
    holder: Optional[str]
    notice: Optional[dict]
    note: str


def rerecord_paths(root: Path, profile, card_id: str, add: list, remove: list, caller=None) -> PathsChange:
    """`card paths <card> --add ... --remove ...`: record the card's Paths as the recorded set plus `add` minus `remove`.
    `caller`: the session id of the lock gate's one-use permit; None for the owner's terminal. Refusals: `card-unknown`,
    `paths-not-lead`, `paths-not-orderer`, `paths-by-holder`, `paths-card-state` (the owner's terminal meets only the
    last), `card-paths-too-wide` (an entry of `add`, or the file's, or an empty result: the first open's own check),
    `paths-file-differs` (the card file's Paths are not the recorded set plus and minus the named entries: nothing is
    recorded), `paths-record-failed`, `card-bad-move` (the card changed while it was being re-recorded). One row in
    PATHS_FILE and one `notice` to the holder, when there is one."""
    import leads  # leads imports this module
    import messages  # messages imports this module
    state, shared = profiles.state_dir(Path(root), profile), profiles.shared_state_dir(Path(root), profile)
    row = register.find(register.read(root, profile), card_id)
    if row is None:
        raise CardError(f"{card_id} is not in the register", reason="card-unknown")
    ordered = row.get(register.ORDERED) or register.OWNER
    holder = records.holders(state, register.closed_ids(root, profile)).get(card_id)
    who = caller or register.OWNER
    problem = paths_problem_for(root, profile, row, caller) if caller else paths_state_problem(row)
    if problem:
        raise CardError(problem[1], reason=problem[0])
    add_raw, remove_raw = paths_entries(", ".join(add)), paths_entries(", ".join(remove))
    wide = wide_entries(add_raw, profile)
    if wide:
        raise wide_error(card_id, wide)
    add_set, remove_set = {norm_entry(x) for x in add_raw}, {e for e in (norm_entry(x) for x in remove_raw) if e}
    if add_set & remove_set:
        raise CardError(f"{card_id}: {_show(add_set & remove_set)} is named by both --add and --remove; name each entry once")
    recorded = paths_set(row.get("paths", ""))
    expected = (recorded | add_set) - remove_set
    try:
        in_file = paths_set(card_paths(root, profile, card_id))
    except OSError as exc:
        raise CardError(f"{card_id}: the card file cannot be read ({exc.__class__.__name__}), so its Paths cannot be "
                        f"compared; nothing was recorded") from None

    def differs(found):
        return CardError(f"{card_id}: the Paths in the card file are not the recorded set plus and minus the entries this "
                         f"call names, so nothing was recorded. Recorded: {_show(recorded)}. This call: add "
                         f"{_show(add_set)}, remove {_show(remove_set)}. Expected in the file: {_show(expected)}. In the "
                         f"file and not expected: {_show(found - expected)}; expected and not in the file: "
                         f"{_show(expected - found)}. The holder or the owner puts the Paths cell of the card file right "
                         f"(the lead cannot write the file after the open), then the lead repeats the same call",
                         reason="paths-file-differs")

    if in_file != expected:
        raise differs(in_file)
    if expected == recorded:
        return PathsChange(card_id, tuple(sorted(recorded)), tuple(sorted(recorded)), who, holder, None, "")
    if not expected:
        raise CardError(f"{card_id}: removing every entry leaves an empty Paths, which is no file rule and names the whole "
                        f"repository; name the files and folders the card edits", reason="card-paths-too-wide")
    new = recorded_paths(root, profile, card_id)  # the first open's own check and form, on the file just compared
    if paths_set(new) != expected:
        raise differs(paths_set(new))
    entry = {"time": logs.now().isoformat(timespec="milliseconds"), "card": card_id, "old": sorted(recorded),
             "new": sorted(expected), "by": who}

    def mutate(rows):
        r = register.find(rows, card_id)
        if (r is None or r.get("status") != row.get("status") or paths_set(r.get("paths", "")) != recorded
                or (r.get(register.ORDERED) or register.OWNER) != ordered):
            raise CardError(f"{card_id} changed while its Paths were being re-recorded; run it again", reason="card-bad-move")
        try:  # the record is written before the register changes
            logs.append_jsonl(Path(state) / PATHS_FILE, entry)
        except OSError as exc:
            raise CardError(f"{card_id}: the record of this re-record could not be written to {Path(state) / PATHS_FILE} "
                            f"({exc.__class__.__name__}), so nothing was recorded. Make the state folder writable (free "
                            f"space, rights, no folder in place of that file), then repeat the call",
                            reason="paths-record-failed") from None
        r["paths"] = new
        return rows
    register.write(root, profile, mutate)
    notice, note = None, ""
    if holder:
        body = (f"{card_id}: the Paths of the card were re-recorded by {who}. Added: {_show(expected - recorded)}. "
                f"Removed: {_show(recorded - expected)}. Recorded now: {_show(expected)}. Your edits of the added files "
                f"pass the card rules from now on; a removed file is no longer in the card")
        try:
            notice = messages.send_paths_notice(shared, who, holder, body, card_id)
        except (OSError, leads.LeadError, messages.MessageError) as exc:
            note = (f"the notice to the holder {holder} could not be written ({exc.__class__.__name__}); the Paths are "
                    f"recorded: tell the holder yourself")
    return PathsChange(card_id, tuple(sorted(recorded)), tuple(sorted(expected)), who, holder, notice, note)


def move(root: Path, profile, card_id: str, target: str, *, session: bool, record_paths: bool,
         light: bool = False, closer: Optional[str] = None, state=None, opener: Optional[str] = None) -> str:
    """Move a card along the chain; returns the status written. `waiting` from the owner's terminal is written
    `waiting-owner`. Refusals: `card-bad-move`, `close-row-without-test`, `card-paths-too-wide`. `closer` (MW-011) is
    the session id of a close by the card's orderer: the orderer, holder, status and test checks run here, with
    `state` the state folder; refusals `close-not-orderer`, `close-by-holder`, `close-tests-failing`. `opener`
    (MW-028) is the session id of a registered lead's open of a proposed card it ordered; the Paths are recorded as at
    the owner's open."""
    row = register.find(register.read(root, profile), card_id)
    if row is None:
        raise CardError(f"{card_id} is not in the register", reason="card-unknown")
    status = row.get("status", "")
    allowed = allowed_moves(status, session and (not light or closer is not None or opener is not None))
    if target not in SET_TARGETS or target not in allowed:
        raise CardError(f"{card_id} is {status}; allowed moves: {', '.join(allowed) or 'none'}",
                        reason="card-bad-move")
    write = "waiting-owner" if target == "waiting" and not session else target
    ordered = row.get(register.ORDERED) or register.OWNER
    if opener is not None:
        import leads  # leads imports this module
        if target != "open":
            raise CardError("only an open is made by a lead as orderer", reason="card-bad-move")
        problem = open_problem(row, opener, leads.is_lead(profiles.shared_state_dir(root, profile), opener))
        if problem:
            raise CardError(problem[1], reason=problem[0])
    if closer is not None:
        if target != "closed":
            raise CardError("only a close is made by an orderer", reason="card-bad-move")
        problem = orderer_problem(row, records.holders(state, register.closed_ids(root, profile)), closer)
        if problem:
            raise CardError(problem[1], reason=problem[0])
        if status not in ("open", "waiting"):
            raise CardError(f"{card_id} is {status}; the orderer closes an open or waiting card",
                            reason="card-bad-move")
        text = card_file(root, profile, card_id).read_text(encoding="utf-8")
        problem = close_problem(root, profile, card_id)
        inherited = False
        if problem is None:
            unchecked_outbox(root, profile, card_id, text)  # MW-019: before the tests run
            unbuilt_deliverables(root, profile, card_id, text)  # MW-020
            unverdicted_tests(root, profile, card_id, text)  # MW-068: before the tests run
            nodes, inherited = close_nodes(root, profile, card_id, text)  # MW-108: the card's inherited red runs too
            problem = tests_problem(root, profile, nodes)
        if problem:
            raise CardError(f"{card_id} cannot close: {problem}. Every Acceptance row's test must pass now (a missing "
                            f"test is a failure): fix the code or the row, then close again"
                            + (f". The red this card inherited at its take must pass too; its orderer may release one id "
                               f"to another open card: `mkway card release-red <test id> --to <card id>`"
                               if inherited else ""), reason="close-tests-failing")
    if target == "closed" and closer is None:
        problem = close_problem(root, profile, card_id)
        if problem:
            raise CardError(f"{card_id} cannot close: {problem}. Every Acceptance row names a test node under the "
                            f"test roots", reason="close-row-without-test")
        text = card_file(root, profile, card_id).read_text(encoding="utf-8")
        unchecked_outbox(root, profile, card_id, text)
        unbuilt_deliverables(root, profile, card_id, text)  # MW-020
        unverdicted_tests(root, profile, card_id, text)  # MW-068
    # H1 (R54), close-fix 10 (A(c)): Paths are recorded once, at the first open from `proposed`; a re-open (`card open`
    # of an open card, or from `waiting`, `waiting-owner` or `closed`) never records them, light mode included. The
    # decision reads the sealed register's status only: no env, no profile, no command. `record_paths` is kept for
    # the callers and no longer read.
    record = status == "proposed"
    paths = recorded_paths(root, profile, card_id) if target == "open" and record else None

    def mutate(rows):
        r = register.find(rows, card_id)
        if r is None or r.get("status") != status:
            raise CardError(f"{card_id} changed while it was being moved; try again", reason="card-bad-move")
        if (closer is not None or opener is not None) and (r.get(register.ORDERED) or register.OWNER) != ordered:
            raise CardError(f"{card_id}: the order was changed while the card was being moved; run it again",
                            reason="close-not-orderer")
        r["status"] = write
        if paths is not None:
            r["paths"] = paths
        return rows
    register.write(root, profile, mutate)
    if opener is not None:
        try:
            text = f"opened by {opener}; ordered by {ordered}"
            append_log_row(root, profile, card_id, "open", text)
            ledger.add(root, profile, card=card_id, topic="card open", quote=text, source=f"card {card_id} open",
                       by=f"session:{opener}")  # MW-049: the lead that ran the move, never the owner's label
        except OSError as exc:
            raise CardError(f"{card_id} is open, but its Log row could not be written ({exc.__class__.__name__}): "
                            f"{card_file(root, profile, card_id)} is not written; "
                            f"the owner adds the row «opened by {opener}; ordered by {ordered}»",
                            reason="close-log-failed")
    if closer is not None:
        try:
            text = f"closed by {closer}; ordered by {ordered}"
            append_log_row(root, profile, card_id, "close", text)
            ledger.add(root, profile, card=card_id, topic="card close", quote=text, source=f"card {card_id} close",
                       by=f"session:{closer}")  # MW-049: the orderer that ran the move, never the owner's label
        except OSError as exc:
            raise CardError(f"{card_id} is closed, but its Log row could not be written ({exc.__class__.__name__}): "
                            f"{card_file(root, profile, card_id)} is not written; "
                            f"the owner adds the row «closed by {closer}; ordered by {ordered}»",
                            reason="close-log-failed")
    return write

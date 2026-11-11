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
from pathlib import Path
from typing import Optional

import ledger
import logs
import outbox
import profiles
import records
import register
import runner

ENGINE_COPY = Path(__file__).resolve().parent.parent  # the copy (or the engine repository) this code belongs to


class CardError(Exception):
    def __init__(self, message: str, reason: str = "card-error"):
        super().__init__(message)
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


def recorded_paths(root: Path, profile, card_id: str) -> str:
    """The card's Paths as the register records them at `card open`; `card-paths-too-wide` refuses."""
    raw = [x for x in re.split(r"[,;]", card_paths(root, profile, card_id)) if x.strip().strip("`").strip()]
    roots = test_roots(profile)
    wide = [x.strip() for x in raw if _too_wide(norm_entry(x), roots)]
    if wide:
        raise CardError(f"{card_id}: Paths entry {', '.join(wide)} names the whole repository or a test root; name "
                        f"the files and folders the card edits", reason="card-paths-too-wide")
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


def approver(profile) -> str:
    """`orderer` or `owner-only` (the default): who makes a session's `card close` pass (`cards.approver`)."""
    cards = profile.get("cards") if isinstance(profile, dict) else None
    return "orderer" if isinstance(cards, dict) and cards.get("approver") == "orderer" else "owner-only"


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
FAILED = re.compile(r"^(?:FAILED|ERROR) (\S+)", re.M)
OWNER_TERMINAL = "the owner closes it in their own terminal"


def _permit_file(state, card_id: str) -> Optional[Path]:
    if not isinstance(card_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", card_id):
        return None
    return Path(state) / PERMITS / f"close-{card_id}.json"


def issue_close_permit(state, card_id: str, session) -> bool:
    """Leave the one-use permit of a close: the card and the session id the hook input gave."""
    target = _permit_file(state, card_id)
    if target is None or not isinstance(session, str) or not session.strip():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps({"card": card_id, "session_id": session,
                               "time": logs.now().isoformat(timespec="milliseconds")}), encoding="utf-8")
    os.replace(tmp, target)
    return True


def take_close_permit(state, card_id: str) -> Optional[str]:
    """The session id of the card's permit, once: the file is removed whatever it holds. None when there is none, it
    is older than PERMIT_SECONDS, or it cannot be read."""
    target = _permit_file(state, card_id)
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


def tests_problem(root: Path, profile, nodes: list) -> Optional[str]:
    """None when `python -m pytest <nodes>` passes now in the root; else why not (the red ids, or the tail)."""
    if not nodes:
        return None
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
        return f"the tests did not finish within {CLOSE_TEST_SECONDS} s"
    if code == 0:
        return None
    text = (out or b"").decode("utf-8", "replace") + "\n" + (err or b"").decode("utf-8", "replace")
    failing = [f.replace("\\", "/") for f in FAILED.findall(text)]  # the card's form of a node id
    if failing:
        return f"{len(failing)} failing: " + "; ".join(failing[:10])
    tail = [ln.strip() for ln in text.splitlines() if ln.strip()][-3:]
    return f"the run exited {code} and named no failing test ({' | '.join(tail)[:300]})"


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


def move(root: Path, profile, card_id: str, target: str, *, session: bool, record_paths: bool,
         light: bool = False, closer: Optional[str] = None, state=None) -> str:
    """Move a card along the chain; returns the status written. `waiting` from the owner's terminal is written
    `waiting-owner`. Refusals: `card-bad-move`, `close-row-without-test`, `card-paths-too-wide`. `closer` (MW-011) is
    the session id of a close by the card's orderer: the orderer, holder, status and test checks run here, with
    `state` the state folder; refusals `close-not-orderer`, `close-by-holder`, `close-tests-failing`."""
    row = register.find(register.read(root, profile), card_id)
    if row is None:
        raise CardError(f"{card_id} is not in the register", reason="card-unknown")
    status = row.get("status", "")
    allowed = allowed_moves(status, session and (not light or closer is not None))
    if target not in SET_TARGETS or target not in allowed:
        raise CardError(f"{card_id} is {status}; allowed moves: {', '.join(allowed) or 'none'}",
                        reason="card-bad-move")
    write = "waiting-owner" if target == "waiting" and not session else target
    ordered = row.get(register.ORDERED) or register.OWNER
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
        if problem is None:
            unchecked_outbox(root, profile, card_id, text)  # MW-019: before the tests run
            unbuilt_deliverables(root, profile, card_id, text)  # MW-020
            problem = tests_problem(root, profile, test_nodes(text))
        if problem:
            raise CardError(f"{card_id} cannot close: {problem}. Every Acceptance row's test must pass now (a missing "
                            f"test is a failure): fix the code or the row, then close again",
                            reason="close-tests-failing")
    if target == "closed" and closer is None:
        problem = close_problem(root, profile, card_id)
        if problem:
            raise CardError(f"{card_id} cannot close: {problem}. Every Acceptance row names a test node under the "
                            f"test roots", reason="close-row-without-test")
        text = card_file(root, profile, card_id).read_text(encoding="utf-8")
        unchecked_outbox(root, profile, card_id, text)
        unbuilt_deliverables(root, profile, card_id, text)  # MW-020
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
        if closer is not None and (r.get(register.ORDERED) or register.OWNER) != ordered:
            raise CardError(f"{card_id}: the order was changed while the tests ran; close it again",
                            reason="close-not-orderer")
        r["status"] = write
        if paths is not None:
            r["paths"] = paths
        return rows
    register.write(root, profile, mutate)
    if closer is not None:
        try:
            text = f"closed by {closer}; ordered by {ordered}"
            append_log_row(root, profile, card_id, "close", text)
            ledger.add(root, profile, card=card_id, topic="card close", quote=text, source=f"card {card_id} close")
        except OSError as exc:
            raise CardError(f"{card_id} is closed, but its Log row could not be written ({exc.__class__.__name__}); "
                            f"the owner adds the row «closed by {closer}; ordered by {ordered}»",
                            reason="close-log-failed")
    return write

"""The card register and its seal (card MW-003, deliverables 3 and 4; R18, R19a, R19c).

The register is `<bundle.root>/cards/REGISTER.md`, a table whose column names are profile strings
(`register.columns`, default Id, Title, Status, Paths, Folder). It is tracked (R18) and written only by the engine's
own commands, with `\\n` line ends. Card MW-011: an optional sixth column (default `Ordered by`) holds the session id
that ordered the card, or `owner`; it is inside the seal like every cell, a register without it reads every card as
`owner`, and only the owner's `card resync --add-ordered-by` adds it to a register that has none.

The seal: `<state.dir>/register.sha` holds the sha256 of the register's bytes, `<state.dir>/register.last` its
content. Every engine write first checks the seal (`register-tampered` on a difference, nothing changed), then
writes the seal and the copy (write-to-temp then replace) and only then replaces the register. One writer at a time
(R19c): `<state.dir>/register.lock`, created exclusively with a random token, held from the seal check to the last
replace; a lock older than 30 s is stale and is taken over; a writer whose lock was taken over refuses
(`register-busy`); a second writer waits up to 5 s, then refuses. Card MW-054: a MISSING seal (a new git work tree
copy never has it: the state folder is untracked) is made by the first reader when the register equals its HEAD
version, line ends aside; git is the authority then, one `log` row says so, and a seal that exists and differs, or a
register that differs from HEAD with no seal, stays `register-tampered`. The way out of `register-tampered` is the
owner's `mkway card resync`. Decided limit: two coordinated undetected writes (the register and `register.sha`) defeat the
seal; review of the register's row diff is the backstop.
"""
from __future__ import annotations

import difflib
import hashlib
import os
import secrets
import time
from pathlib import Path
from typing import Callable, Optional

import profiles

DEFAULT_COLUMNS = ["Id", "Title", "Status", "Paths", "Folder"]
KEYS = ("id", "title", "status", "paths", "folder")
# Card MW-011: the sixth column, who ordered the card. A row without the cell reads `owner`; the column is written
# only when the register already has it, or (a new register) when the profile names six columns or has
# `cards.approver: orderer`, so a register of five columns is never migrated by a write.
ORDERED = "ordered"
OWNER = "owner"
DEFAULT_ORDERED_COLUMN = "Ordered by"
STATUSES = ("proposed", "open", "waiting", "waiting-owner", "closed")
TITLE = "# Card register"
STALE_SECONDS = 30
WAIT_SECONDS = 5
OWNER_FIX = "run `python mkway/engine/mkway.py card resync` in your own terminal"


class RegisterError(Exception):
    def __init__(self, reason: str, message: str):
        super().__init__(f"{reason}: {message}")
        self.reason = reason
        self.message = message


def path(root, profile) -> Path:
    return Path(root) / profiles.bundle_root(profile) / "cards" / "REGISTER.md"


def _state(root, profile) -> Path:
    return profiles.state_dir(root, profile)


def sha_path(root, profile) -> Path:
    return _state(root, profile) / "register.sha"


def last_path(root, profile) -> Path:
    return _state(root, profile) / "register.last"


def lock_path(root, profile) -> Path:
    return _state(root, profile) / "register.lock"


def _named(profile):
    """The profile's `register.columns` when it is five or six non-empty names, else None."""
    reg = profile.get("register") if isinstance(profile, dict) else None
    cols = reg.get("columns") if isinstance(reg, dict) else None
    if isinstance(cols, list) and len(cols) in (len(KEYS), len(KEYS) + 1) and \
            all(isinstance(c, str) and c.strip() for c in cols):
        return [c.strip() for c in cols]
    return None


def columns(profile) -> list:
    """The five column names of id, title, status, paths, folder."""
    named = _named(profile)
    return named[:len(KEYS)] if named else list(DEFAULT_COLUMNS)


def orderer_column(profile) -> str:
    """The name of the sixth column: the profile's sixth name, else `Ordered by`."""
    named = _named(profile)
    return named[len(KEYS)] if named and len(named) > len(KEYS) else DEFAULT_ORDERED_COLUMN


def wants_orderer(profile) -> bool:
    """A new register has the sixth column when the profile names six columns or `cards.approver` is `orderer`."""
    named = _named(profile)
    cards = profile.get("cards") if isinstance(profile, dict) else None
    return bool(named and len(named) > len(KEYS)) or (isinstance(cards, dict) and cards.get("approver") == "orderer")


def _header_cells(text: str, profile):
    """The cells of the register's header line, or None when the text has none."""
    first = columns(profile)[0]
    for line in text.splitlines():
        if line.startswith("|") and _cells(line) and _cells(line)[0] == first:
            return _cells(line)
    return None


def file_has_orderer(root, profile):
    """True or False: does the register file's header name the sixth column; None when there is no register or no
    header (a new register)."""
    p = path(root, profile)
    if not p.is_file():
        return None
    header = _header_cells(p.read_text(encoding="utf-8"), profile)
    return None if header is None else orderer_column(profile) in header


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _cells(line: str) -> list:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse(text: str, profile) -> list:
    """Rows as dicts (id, title, status, paths, folder, ordered) read by the header's column names. `ordered` is
    `owner` when the register has no such column or the cell is blank."""
    names = columns(profile)
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("|") and _cells(line) and _cells(line)[0] == names[0]:
            header = _cells(line)
            index = {key: (header.index(name) if name in header else None) for key, name in zip(KEYS, names)}
            ordered_at = header.index(orderer_column(profile)) if orderer_column(profile) in header else None
            out = []
            for row in lines[i + 1:]:
                if not row.startswith("|"):
                    continue  # MW-082: a stray line (a merge can leave one) loses no row after it
                cells = _cells(row)
                if set(row) <= set("|-: "):
                    continue
                one = {k: (cells[j] if j is not None and j < len(cells) else "") for k, j in index.items()}
                who = cells[ordered_at] if ordered_at is not None and ordered_at < len(cells) else ""
                one[ORDERED] = who or OWNER
                out.append(one)
            return out
    return []


def render(rows: list, profile, with_orderer=None) -> str:
    """The register text. The sixth column is written when `with_orderer` is true (None: the profile's reading)."""
    names = columns(profile)
    if with_orderer is None:
        with_orderer = wants_orderer(profile)
    if with_orderer:
        names = names + [orderer_column(profile)]
    out = [TITLE, "", "| " + " | ".join(names) + " |", "|" + "---|" * len(names)]
    for r in rows:
        cells = [str(r.get(k, "") or "").replace("|", "/") for k in KEYS]
        if with_orderer:
            cells.append(str(r.get(ORDERED, "") or OWNER).replace("|", "/"))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def read(root, profile) -> list:
    p = path(root, profile)
    return parse(p.read_text(encoding="utf-8"), profile) if p.is_file() else []


def _lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def seal_verdict(seal: Optional[str], working: Optional[bytes], committed: Optional[bytes]) -> str:
    """The seal's decision from values only (card MW-054): `ok`, `differs` (a seal that exists names other bytes),
    `register-missing` (a seal and no register), `adopt` (no seal, and the register equals its committed HEAD version,
    line ends aside: a checkout may convert them) or `missing` (no seal, and the register differs from HEAD or is not
    committed). A seal that exists is never adopted over, whatever HEAD holds."""
    if seal is None:
        if working is None:
            return "ok"
        return "adopt" if committed is not None and _lf(working) == _lf(committed) else "missing"
    if working is None:
        return "register-missing"
    return "ok" if seal.strip() == digest(working) else "differs"


def _committed(root, profile) -> Optional[bytes]:
    """The register as the HEAD commit of the root's own work tree holds it, or None (no git, no commit, not tracked,
    git too slow). Read-only: `git show HEAD:./<register>` from the root."""
    if profiles.vcs(profile) != "git":
        return None
    try:
        import runner
        rel = path(root, profile).relative_to(Path(root)).as_posix()
        proc = runner.git(root, "show", f"HEAD:./{rel}", text=False)
    except Exception:
        return None
    return proc.stdout if proc.returncode == 0 else None


def _adopt(root, profile, working: bytes, locked: bool = False) -> bool:
    """Make the seal of a register that equals its committed version (a new git work tree copy has none: the seal is
    untracked state). Git is the authority here (ruled 2026-11-12). Under the register lock (`locked`: the caller
    holds it already), the seal is checked again first; the file's own bytes are sealed, with the copy of the register
    beside it, and one `log` row says so. False when it could not be made (the caller then reports the missing
    seal)."""
    lock = lock_path(root, profile)
    token = None
    if not locked:
        try:
            token = _acquire(lock)
        except (RegisterError, OSError):
            return False
    try:
        reg, sha = path(root, profile), sha_path(root, profile)
        if sha.exists() or not reg.is_file() or reg.read_bytes() != working:
            return False  # another writer sealed it, or the register moved: nothing is adopted
        _replace(sha, digest(working).encode("ascii"))
        _replace(last_path(root, profile), working)
        try:
            import logs
            logs.write_refusal(_state(root, profile), logs.row(
                session=None, event="seal", tool=None, gate="register", reason_id="register-seal-adopted",
                target=reg.relative_to(Path(root)).as_posix(), kind="log", source="HEAD", sha256=digest(working)))
        except OSError:
            pass  # the seal stands; a row that cannot be written changes no verdict
        return True
    except OSError:
        return False
    finally:
        if token is not None:
            _release(lock, token)


def seal_problem(root, profile, *, _locked: bool = False) -> Optional[str]:
    """None when the seal holds: no register and no seal, or the seal equals the register's sha256. MW-054: a MISSING
    seal is made here, once, when the register equals its HEAD version (a git work tree copy); every other case reads
    as before. `_locked`: the caller (`write`) holds the register lock already."""
    reg, sha = path(root, profile), sha_path(root, profile)
    working = reg.read_bytes() if reg.is_file() else None
    seal = sha.read_text(encoding="utf-8") if sha.is_file() else None
    committed = _committed(root, profile) if seal is None and working is not None else None
    verdict = seal_verdict(seal, working, committed)
    if verdict == "adopt":
        verdict = "ok" if _adopt(root, profile, working, _locked) else "missing"
    return {"ok": None, "missing": f"{sha.name} is missing", "register-missing": "the register is missing",
            "differs": "the register differs from its seal"}[verdict]


def check(root, profile, *, _locked: bool = False) -> None:
    problem = seal_problem(root, profile, _locked=_locked)
    if problem:
        raise RegisterError("register-tampered", f"{problem}; nothing is edited or committed until the owner "
                                                 f"checks it: {OWNER_FIX}")


def _replace(target: Path, data: bytes) -> None:
    tmp = target.with_name(target.name + f".{secrets.token_hex(4)}.tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, target)


def _acquire(lock: Path) -> str:
    token = secrets.token_hex(16)
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + WAIT_SECONDS
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(token)
            return token
        except FileExistsError:
            try:
                stale = time.time() - lock.stat().st_mtime > STALE_SECONDS
            except OSError:
                stale = False
            if stale:
                _replace(lock, token.encode("utf-8"))
                return token
            if time.monotonic() > deadline:
                raise RegisterError("register-busy", "another writer holds the register lock; try again")
            time.sleep(0.05)


def _holds(lock: Path, token: str) -> bool:
    try:
        return lock.read_text(encoding="utf-8") == token
    except OSError:
        return False


def _release(lock: Path, token: str) -> None:
    if _holds(lock, token):
        try:
            os.remove(lock)
        except OSError:
            pass


def write(root, profile, mutate: Callable[[list], list], *, _before_replace=None) -> list:
    """Apply `mutate` to the rows under the lock and the seal check; returns the new rows."""
    lock = lock_path(root, profile)
    token = _acquire(lock)
    try:
        check(root, profile, _locked=True)
        new_rows = mutate(read(root, profile))
        has = file_has_orderer(root, profile)  # the file's own header decides; a new register follows the profile
        data = render(new_rows, profile, wants_orderer(profile) if has is None else has).encode("utf-8")
        if _before_replace is not None:
            _before_replace()
        if not _holds(lock, token):
            raise RegisterError("register-busy", "the register lock was taken over by another writer; nothing "
                                                 "was changed; try again")
        try:
            reg = path(root, profile)
            reg.parent.mkdir(parents=True, exist_ok=True)
            _replace(sha_path(root, profile), digest(data).encode("ascii"))
            _replace(last_path(root, profile), data)
            _replace(reg, data)
        except OSError as exc:
            raise RegisterError("register-write-failed", f"{exc.__class__.__name__}; {OWNER_FIX}") from None
        return new_rows
    finally:
        _release(lock, token)


BASELINE = "card_baseline.json"


def write_baseline(root, profile) -> None:
    """The baseline of the start line's card changes (M1): the register's statuses and the time, written only by the
    owner's re-seal (`card resync`) and by install's seal; never at a start or a compaction."""
    import json
    import logs
    rows = read(root, profile)
    data = {"time": logs.now().isoformat(timespec="milliseconds"), "status": {r["id"]: r.get("status", "")
                                                                                for r in rows}}
    target = _state(root, profile) / BASELINE
    target.parent.mkdir(parents=True, exist_ok=True)
    _replace(target, (json.dumps(data) + "\n").encode("utf-8"))


def read_baseline(root, profile):
    """The baseline written by `write_baseline`, or None when there is none or it cannot be read."""
    import json
    try:
        data = json.loads((_state(root, profile) / BASELINE).read_text(encoding="utf-8"))
        if isinstance(data.get("status"), dict) and isinstance(data.get("time"), str):
            return data
    except (OSError, ValueError, AttributeError):
        pass
    return None


def closed_ids(root, profile) -> set:
    """The closed card ids of the register; empty when it cannot be read (the strict reading for the records)."""
    try:
        return {r["id"] for r in read(root, profile) if r.get("status") == "closed"}
    except (OSError, ValueError):
        return set()


def find(rows: list, card_id: str) -> Optional[dict]:
    for r in rows:
        if r.get("id") == card_id:
            return r
    return None


def set_status(root, profile, card_id: str, status: str, paths: Optional[str] = None) -> list:
    if status not in STATUSES:
        raise RegisterError("card-bad-move", f"unknown status {status!r}")

    def mutate(rows):
        r = find(rows, card_id)
        if r is None:
            raise RegisterError("card-unknown", f"{card_id} is not in the register")
        r["status"] = status
        if paths is not None:
            r["paths"] = paths
        return rows
    return write(root, profile, mutate)


def set_ordered(root, profile, card_id: str, who: str, *, only_owner: bool = False) -> list:
    """Write the `Ordered by` cell of one card through the sealed writer. `only_owner`: change it only while it still
    reads `owner` (the `post` group's step after a session's `card new`). The register must have the column."""
    def mutate(rows):
        r = find(rows, card_id)
        if r is None:
            raise RegisterError("card-unknown", f"{card_id} is not in the register")
        if not only_owner or r.get(ORDERED, OWNER) == OWNER:
            r[ORDERED] = who
        return rows
    return write(root, profile, mutate)


def reseal(root, profile, add_orderer: bool = False) -> list:
    """The owner's `card resync`: the diff of the register against `register.last`, then a new seal. Returns the
    diff lines. `add_orderer` (the owner's `--add-ordered-by`): first add the sixth column to a register that has
    none, every row `owner`."""
    lock = lock_path(root, profile)
    token = _acquire(lock)
    try:
        reg = path(root, profile)
        now = reg.read_bytes() if reg.is_file() else b""
        if add_orderer and file_has_orderer(root, profile) is False:
            now = render(parse(now.decode("utf-8"), profile), profile, True).encode("utf-8")
            _replace(reg, now)
        last = last_path(root, profile)
        before = last.read_bytes() if last.is_file() else b""
        diff = list(difflib.unified_diff(before.decode("utf-8", "replace").splitlines(),
                                         now.decode("utf-8", "replace").splitlines(),
                                         fromfile="register.last", tofile="REGISTER.md", lineterm=""))
        _replace(sha_path(root, profile), digest(now).encode("ascii"))
        _replace(last, now)
        write_baseline(root, profile)  # M1: only the owner's re-seal moves the card-change baseline
        return diff
    finally:
        _release(lock, token)

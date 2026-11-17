"""Shared fixture of the MW-134 shell tests (retirement of a recorded red id). Not a test module. Synthetic names only.

The world (`world`): a pytest project with one open card CARD-001 held by session s1. Two commits of the card's test file,
made with plain git, each with the red-record row the gate would have written (`seed`): the first records `OLD` red, the
second renames it in the file to `NEW` and records `NEW` red. So the record holds both ids, `OLD` is gone from the tree, and a
code commit is refused `red-ids-still-red` for it: the real order of events of R348 1."""
import datetime
import json
from pathlib import Path

import _engine  # noqa: F401  (puts the engine folder on the import path)
from _commit_project import git, run_gate, stage
from _engine import jsonl
from _red_project import APP_MUL, RED_MUL, card_file, red_project

CARD = "CARD-001"
SESSION = "s1"  # the session that holds the card (the builder)
LEAD = "session:lead-1"  # the `by` of a decision another session wrote
NEW_FILE = "tests/test_new.py"
OLD = f"{NEW_FILE}::test_mul"
NEW = f"{NEW_FILE}::test_mul_v2"
V1 = RED_MUL
V2 = 'import app\n\n\ndef test_mul_v2():\n    """Catches: mul is missing."""\n    assert app.mul(2, 3) == 6\n'
V2_RED = V2.replace("== 6", "== 7")  # fails with the code at HEAD
RED_AGAIN = V1.replace("== 6", "== 7")  # test_mul again, failing
BOTH = RED_AGAIN + "\n\n" + V2.split("\n\n\n", 1)[1]  # test_mul (failing) and test_mul_v2 in one file
BROKEN = "def test_mul_v2(:\n    pass\n"  # a file that does not parse
IMPORT_ERROR = "import no_such_module_anywhere\n\n\ndef test_mul_v2():\n    assert True\n"
CODE2 = APP_MUL + "\n\nVERSION = 1\n"
LINE = f"{OLD} -> {NEW}"
DROPPED = f"{OLD} -> dropped: the requirement changed"
SAY = f"{CARD} retire the old test under D-1"  # a message that names the decision D-1 (the ledger's first row)
CODE = "def add(a, b):\n    return a + b\n"


def commit(text):
    """`git commit -m <text>` as the commit command of a gate call."""
    return f'git commit -m "{text}"'


def red_file(root) -> Path:
    return Path(root) / "mkway" / "state" / "red_proof.jsonl"


def record_rows(root) -> list:
    return jsonl(red_file(root)) if red_file(root).is_file() else []


def retire_rows(root) -> list:
    return [r for r in record_rows(root) if "retired" in r]


def map_rel(root) -> str:
    """The card's case_map.md, relative to the task root."""
    return card_file(root).parent.relative_to(Path(root)).as_posix() + "/case_map.md"


def seed(root, red=()) -> None:
    """The red-record row of the commit at HEAD, as the gate writes it (its git tree), for the ids in `red`."""
    tree = git(root, "rev-parse", "HEAD^{tree}").strip()
    row = {"time": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds"), "session": SESSION,
           "card": CARD, "tree": tree, "git_tree": tree, "red": list(red), "pins": [], "checks": [], "missing": {},
           "would_refuse": [], "mode": "trip"}
    path = red_file(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def plain_commit(root, rel, text, message="CARD-001 step"):
    stage(root, rel, text)
    git(root, "commit", "-q", "-m", message)


def world(tmp_path, **over):
    """OLD recorded red at one commit, NEW at the next, the file holding only NEW: see the module text. The code is at HEAD
    already, so the suite is green there and a tests-only commit is not stopped by an old red."""
    root = red_project(tmp_path, **over)
    plain_commit(root, "app.py", APP_MUL, "CARD-001 code")
    plain_commit(root, NEW_FILE, V1, "CARD-001 red one")
    seed(root, [OLD])
    plain_commit(root, NEW_FILE, V2, "CARD-001 red two")
    seed(root, [NEW])
    return root


def profile_of(root) -> dict:
    return json.loads((Path(root) / "mkway" / "profile.json").read_text(encoding="utf-8"))


def add_decision(root, by=LEAD, status="in force") -> str:
    """One row of the root's ledger (the file is made by the first row); the id of the row."""
    import ledger
    return ledger.add(root, profile_of(root), card="C", topic="t", quote="q", source="s", by=by, status=status)["id"]


def stage_line(root, line=LINE) -> None:
    stage(root, map_rel(root), line + "\n")


def unstage(root, *rels) -> None:
    git(root, "reset", "-q", "HEAD", "--", *rels)


def code_gate(root):
    """The card's code commit, judged by the gate: a harmless change of app.py (the suite is green at HEAD)."""
    stage(root, "app.py", CODE2)
    return run_gate(root, commit(f"{CARD} code"))


def retire(root, message=SAY, line=LINE):
    """The retirement commit, judged by the gate: only the card's case_map.md is staged."""
    stage_line(root, line)
    return run_gate(root, commit(message))


def made(root, message) -> None:
    """The commit itself, made with git, after the gate allowed it."""
    git(root, "commit", "-q", "-m", message)

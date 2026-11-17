"""Shared fixture of the MW-108 shell tests: a real small git repository with a pytest project, the real card commands
(`card new`, `card open`, `card take`, `card release-red`) run in process, and the commit gate driven in process. Not a
test module. Synthetic names only."""
import json
import re
from pathlib import Path

from _commit_project import git, make_project, run_gate, stage, write
from _engine import cli, jsonl
from _red_project import seed_record
import cardtool
import gate_commit_tests as gct
import records
import register

ORD, HOLD, HOLD2, THIRD = "s-ord", "s-hold", "s-hold2", "s-third"
RED = "def test_{name}():\n    assert False\n"
GREEN = "def test_{name}():\n    assert True\n"
COLLECT_FAIL = "import module_that_is_gone\n\n\ndef test_a():\n    assert True\n"
KEYS = "tests/test_keys.py::test_keys"
TWO = "tests/test_two.py::test_two"
ORPHAN = "tests/test_orphan.py::test_orphan"
ACCEPT = "tests/test_ok.py::test_add"
APP = "def add(a, b):\n    return a + b + {n} - {n}\n"


def state(root) -> Path:
    return Path(root) / "mkway" / "state"


def profile(root) -> dict:
    return json.loads((Path(root) / "mkway" / "profile.json").read_text(encoding="utf-8"))


def project(tmp_path):
    """A task root with one commit, test roots `tests`, the orderer rule on and the verdict check off."""
    return make_project(tmp_path, test_roots=["tests"], cards={"approver": "orderer", "verdicts": "off"})


def commit_file(root, rel, text):
    """A file written, staged and committed with git directly (the test's own step, no gate)."""
    write(root, rel, text)
    git(root, "add", "-f", "--", rel)
    git(root, "commit", "-q", "-m", f"add {rel}")


def remove_file(root, rel):
    git(root, "rm", "-q", "--", rel)
    git(root, "commit", "-q", "-m", f"remove {rel}")


def _card_file(root, card_id) -> Path:
    (folder,) = [p for p in (Path(root) / "mkway" / "cards").iterdir() if p.name.startswith(card_id + "-")]
    return folder / "CARD.md"


def open_card(root, title, paths, ordered_by=ORD) -> str:
    """A card made by the card command, given its Paths and one Acceptance row that names a green test, opened by the
    owner's command, and ordered by `ordered_by` (the register's column)."""
    number = len(list((Path(root) / "mkway" / "cards").glob("CARD-*"))) + 1
    card_id = f"CARD-{number:03d}"
    assert cli(root, "card", "new", title)[0] == 0
    path = _card_file(root, card_id)
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^\| \*\*Paths\*\* \|.*\|$", f"| **Paths** | {paths} |", text, flags=re.M)
    text = re.sub(r"^\| E1 \|.*\|$", f"| E1 | x | a | b | {ACCEPT} |", text, flags=re.M)
    path.write_text(text, encoding="utf-8", newline="\n")
    assert cli(root, "card", "open", card_id)[0] == 0
    if ordered_by:
        def mutate(rows):
            register.find(rows, card_id)[register.ORDERED] = ordered_by
            return rows
        register.write(root, profile(root), mutate)
    return card_id


def hold(root, card_id, session="s1"):
    """The session holds the card (the record the post hook writes) and the card has its red record (MW-072)."""
    records.append(state(root), session, "take", card_id)
    seed_record(root, card_id)


def make_head_row(root):
    """One gate attempt with no card held and a changed app.py: the suite runs on the staged tree and on HEAD, so HEAD's
    tree has a row in `commit_tests_head.jsonl`. The verdict is not read. The working tree is put back."""
    stage(root, "app.py", APP.format(n=7))
    run_gate(root)
    git(root, "reset", "-q", "--", "app.py")
    git(root, "checkout", "-q", "--", "app.py")


def seed_row(root, result, failed=()):
    """A row of the suite on HEAD's tree, as the gate keeps it, written for a tree the gate did not run (setup only)."""
    prof = profile(root)
    argv = gct._argv(prof, cardtool.test_roots(prof))
    row = {"time": "2026-11-16T00:00:00.000+00:00", "session": "s1", "tree": gct.tree_keys(root, "HEAD")[-1],
           "command": " ".join(argv), "profile": gct.profile_key(prof), "reader": gct.READER, "result": result,
           "duration_seconds": 0.1, "failed_count": len(failed), "failing": list(failed), "failed_ids": list(failed),
           "file_errors": {}, "setup_errors": {}}
    path = state(root) / gct.HEAD_FILE
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def take(root, card_id):
    return cli(root, "card", "take", card_id, session=True)


def inherited_rows(root) -> list:
    return jsonl(state(root) / "inherited_red.jsonl")


def release_red(root, test_id, to, session=ORD):
    """`mkway card release-red <id> --to <card>` as a session's shell runs it, after the hook left the by-permit for
    `session`; session None is the owner's terminal. Returns (exit code, stdout, stderr)."""
    if session:
        assert cardtool.issue_by_permit(state(root), session)
    args = ["card", "release-red", test_id, *(["--to", to] if to else [])]
    return cli(root, *args, session=bool(session))


def reason_of(err):
    m = re.search(r"mkway: ([a-z-]+):", err)
    return m.group(1) if m else None


def close_result(root, card_id, closer=ORD):
    """The orderer's close, as `mkway card close` runs it for a session: (`ok`, status) or (reason id, message)."""
    try:
        return "ok", cardtool.move(root, profile(root), card_id, "closed", session=True, record_paths=False,
                                   closer=closer, state=state(root))
    except cardtool.CardError as exc:
        return exc.reason, str(exc)


def two_cards(root):
    """CARD-001 (Paths app.py and tests/test_keys.py) held by HOLD and CARD-002 (tests/test_two.py) held by HOLD2, both
    ordered by ORD; HEAD red in tests/test_keys.py is taken as CARD-001's inherited red when HEAD has a row."""
    first = open_card(root, "Keys", "`app.py`, `tests/test_keys.py`")
    second = open_card(root, "Two", "`tests/test_two.py`")
    return first, second


def hold_both(root, first, second):
    records.append(state(root), HOLD, "take", first)
    records.append(state(root), HOLD2, "take", second)


def set_status(root, card_id, status):
    """The owner's `card set <id> <status>`; the exit code."""
    return cli(root, "card", "set", card_id, status)[0]

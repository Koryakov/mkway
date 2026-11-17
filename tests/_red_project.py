"""Shared fixture for the MW-072 red proof tests (shell on a real small repository, and the real hook). Not a test module.
Synthetic names only."""
import contextlib
import hashlib
import json
import re
import sys
from pathlib import Path

import _template
import records
from _commit_project import FILES, git, make_project
from _engine import cli, jsonl

CARD = "CARD-001"
PATHS = "`app.py`, `app2.py`, `tests/test_new.py`"
OLD_ROW = "| E1 | item id | value today | value after the change | tests/test_x.py::test_y |"

RED_MUL = 'import app\n\n\ndef test_mul():\n    """Catches: mul is missing."""\n    assert app.mul(2, 3) == 6\n'
GREEN = 'from app import add\n\n\ndef test_add_again():\n    """Checks: add sums."""\n    assert add(1, 1) == 2\n'
PIN = 'from app import add\n\n\ndef test_add_again():\n    """Pins: add returns the sum."""\n    assert add(1, 1) == 2\n'
MISSING = "from app2 import mul\n\n\ndef test_mul():\n    assert mul(2, 3) == 6\n"
OUTSIDE = "from nopkg import mul\n\n\ndef test_mul():\n    assert mul(2, 3) == 6\n"
SKIPPED = ('import app\nimport pytest\n\n\ndef test_mul():\n    pytest.skip("x")\n'
           '    assert app.mul(2, 3) == 6\n')
APP_MUL = "def add(a, b):\n    return a + b\n\n\ndef mul(a, b):\n    return a * b\n"
APP2 = "def mul(a, b):\n    return a * b\n"
BROKEN_OLD = "from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 4\n"
PIN_ROW = "| E1 | pinning of add | works | works | tests/test_new.py::test_add_again |"
COMMIT_TEXT = "CARD-001 change"
RED_AND_CHECKS = ('import app\nfrom app import add\n\n\ndef test_mul():\n    """Catches: mul is missing."""\n'
                  '    assert app.mul(2, 3) == 6\n\n\ndef test_add_again():\n    """Checks: add sums."""\n'
                  '    assert add(1, 1) == 2\n')
RED_AND_CATCHES = RED_AND_CHECKS.replace("Checks: add sums.", "Catches: add stops summing.")
REPLAY = ("import app\n\n\n"
          + "".join(f'def test_red{n}():\n    """Catches: mul{n} is missing."""\n    assert app.mul{n}(2, 3) == 6\n\n\n'
                    for n in range(1, 10))
          + "".join(f'def test_guard{n}():\n    """Checks: add {n}."""\n    assert app.add({n}, 1) == {n + 1}\n\n\n'
                    for n in range(1, 5)))


def card_file(root) -> Path:
    return next((Path(root) / "mkway" / "cards").glob("CARD-001-*")) / "CARD.md"


def edit_card(path: Path, *, paths, kind=None, row=None) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^\| \*\*Paths\*\* \|.*\|$", f"| **Paths** | {paths} |", text, flags=re.M)
    if kind:
        text = text.replace(f"| **Paths** | {paths} |", f"| **Paths** | {paths} |\n| **Kind** | {kind} |")
    if row:
        text = text.replace(OLD_ROW, row)
    path.write_text(text, encoding="utf-8", newline="\n")


_TEMPLATE_COPY = []  # the `template_copy` fixture of the running test (R217b), put here by `use_template_copy`


@contextlib.contextmanager
def use_template_copy(template_copy):
    """MW-085's template mechanism for `red_project` (R217b): inside this context each variant of the project is built once
    per worker in the protected template folder, and every test gets a copy of it in its own `tmp_path`."""
    _TEMPLATE_COPY.append(template_copy)
    try:
        yield
    finally:
        _TEMPLATE_COPY.pop()


def _build(base, *, kind, row, name, **over) -> Path:
    root = make_project(base, name=name, **over)
    assert cli(root, "card", "new", "First", session=True)[0] == 0
    edit_card(card_file(root), paths=PATHS, kind=kind, row=row)
    assert cli(root, "card", "open", CARD)[0] == 0
    records.append(root / "mkway" / "state", "s1", "take", CARD)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "card")
    return root


def red_project(tmp_path, *, kind=None, row=None, name="red", **over):
    """A git task root with a pytest project, one open card CARD-001 held by session s1, committed. Inside
    `use_template_copy` it is a copy of a template built once per worker; otherwise it is built in `tmp_path`."""
    if _TEMPLATE_COPY:
        key = hashlib.sha1(json.dumps([kind, row, name, over], sort_keys=True, default=str).encode()).hexdigest()[:10]
        try:
            return _TEMPLATE_COPY[-1](f"red_{key}", lambda folder: _build(folder, kind=kind, row=row, name=name, **over)) / name
        except _template.TemplateHoldsItsPath:
            pass  # a copy would point back at the template: build in this test's own tmp_path
    return _build(tmp_path, kind=kind, row=row, name=name, **over)


def _seed_row(card_id, tree, red) -> dict:
    return {"card": card_id, "tree": tree, "red": list(red), "pins": ["seed"], "checks": [], "missing": {},
            "would_refuse": [], "mode": "trip"}


def seed_record(root, card_id, red=()) -> None:
    """MW-072: a red record row (one pin id, and the ids in `red`) for a card whose red tests an older fixture committed with
    git directly, so the older tests of the new-red judgement are not stopped by `red-not-recorded`. The row's tree is
    HEAD's."""
    import gate_commit_tests
    import logs
    tree = gate_commit_tests.tree_keys(root, "HEAD")[0]
    logs.append_jsonl(Path(root) / "mkway" / "state" / "red_proof.jsonl", _seed_row(card_id, tree, red))


def seed_record_at(root, card_id, git_call, red=()) -> None:
    """The same for a fixture with no project object: `root` is the task root (its state folder lies below it) and
    `git_call(*args)` runs git in the repository and returns its text. R217a: a fixture may seed the record when it is a
    precondition of what it tests and not its subject; it never sets the gate to watch. `red` lists ids the record names as
    red though they never ran red here."""
    tree = git_call("rev-parse", "HEAD^{tree}").strip()
    path = Path(root) / "mkway" / "state" / "red_proof.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(_seed_row(card_id, tree, red)) + "\n")


def seed_record_file(project, card_id, red=()) -> None:
    """The same for an installed project of the real hook tests; the row's tree is HEAD's tree."""
    seed_record_at(project.root, card_id, project.git, red)


class RedFirstError(AssertionError):
    """A step of `commit_red_first` did not make the commit it should have made."""


def commit_red_first(git_call, stage, commit, red, green) -> list:
    """R217: the two-step commit of a card that adds a test with its code, for the fixtures that model a correct card. First
    the tests alone (`red`, a pair: the message and the paths), then the code (`green`). Each step is two calls of the
    caller's own, `stage(paths)` and `commit(message, paths)`, never one chained command (the gate refuses a chained add and
    commit, reason commit-tests-chained). The callables differ per fixture (a return value, a Ran object, an exception) and
    their results are not read: after each step the helper reads git (`git_call(*args)` runs git in the task root) and checks
    that exactly one new commit was made, with that message and holding exactly those paths. Returns the two shas; raises
    `RedFirstError` naming the step."""
    shas = []
    for step, (message, paths) in (("red", red), ("green", green)):
        before = int(git_call("rev-list", "--count", "HEAD").strip())
        stage(list(paths))
        commit(message, list(paths))
        now = int(git_call("rev-list", "--count", "HEAD").strip())
        if now != before + 1:
            raise RedFirstError(f"the {step} commit was not made ({before} commits before, {now} after)")
        subject = git_call("log", "-1", "--format=%s").strip()
        taken = sorted(git_call("show", "--name-only", "--format=", "--relative", "HEAD").split())
        if subject != message or taken != sorted(paths):
            raise RedFirstError(f"the {step} commit holds {taken} under {subject!r}, not {sorted(paths)} under {message!r}")
        shas.append(git_call("rev-parse", "HEAD").strip())
    return shas


def record_rows(root) -> list:
    return jsonl(Path(root) / "mkway" / "state" / "red_proof.jsonl")


def recorded(root) -> list:
    out = []
    for row in record_rows(root):
        out += row.get("red", [])
    return out


def install_red(base, *, kind=None):
    """The real engine installed into a scratch repository (the task folder below the git top), one open card CARD-001
    held by session b1, a pytest project committed. Returns (project, session)."""
    from _hook_driver import decision, install_project
    p = install_project(Path(base))
    p.profile(**{"python.command": sys.executable, "gates.trip": {"min_calls": 100000}})
    p.owner("card", "new", "Red card")
    edit_card(next((p.root / "mkway" / "cards").glob("CARD-001-*")) / "CARD.md", paths=PATHS + ", `tests/test_ok.py`",
              kind=kind)
    p.owner("card", "open", CARD)
    decision(p.fire("SessionStart", "b1"))
    p.session_shell("b1", f"python mkway/engine/mkway.py card take {CARD}")
    for rel, body in FILES.items():
        if rel not in ("README.md", ".gitignore"):
            p.write(rel, body)
    p.git("add", "-f", "--", "pytest.ini", "app.py", "tests/test_ok.py")
    p.git("add", "-A", "mkway/cards", "mkway/profile.json")
    p.git("commit", "-q", "-m", "baseline of the red proof rows")
    return p, "b1"

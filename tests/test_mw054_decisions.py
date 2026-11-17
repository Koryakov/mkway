"""Card MW-054, the decisions as table tests (rows E1 and E2, and the documents row E8). No disk, no git, no hook:
`register.seal_verdict` and `paths.cli_root` read only the values they are given. Synthetic values only."""
from __future__ import annotations

from pathlib import Path

import pytest

import _engine  # noqa: F401  (puts the engine folder on the path)
import paths
import register

REPO = Path(__file__).resolve().parents[1]
D = register.digest

# (case, seal text or None, working register bytes or None, committed (HEAD) bytes or None, verdict)
SEAL_TABLE = [
    ("no register and no seal", None, None, None, "ok"),
    ("no register, no seal, HEAD has one", None, None, b"a", "ok"),
    ("the seal equals the register", D(b"a"), b"a", b"a", "ok"),
    ("the seal text ends with a line end", D(b"a") + "\n", b"a", b"a", "ok"),
    ("the seal differs, the register equals HEAD", D(b"x"), b"a", b"a", "differs"),
    ("the seal differs, the register differs from HEAD", D(b"x"), b"b", b"a", "differs"),
    ("the seal differs, the register is not committed", D(b"x"), b"a", None, "differs"),
    ("no seal, the register equals HEAD", None, b"a", b"a", "adopt"),
    ("no seal, the register equals HEAD apart from the line ends", None, b"a\r\nb\r\n", b"a\nb\n", "adopt"),
    ("no seal, the register differs from HEAD besides the line ends", None, b"a\r\nc\r\n", b"a\nb\n", "missing"),
    ("no seal, the register differs from HEAD", None, b"b", b"a", "missing"),
    ("no seal, the register is not in HEAD", None, b"a", None, "missing"),
    ("no seal, an empty register equals an empty HEAD one", None, b"", b"", "adopt"),
    ("a seal and no register", D(b"a"), None, b"a", "register-missing"),
]


@pytest.mark.parametrize("case,seal,working,committed,verdict", SEAL_TABLE, ids=[row[0] for row in SEAL_TABLE])
def test_the_seal_verdict_table(case, seal, working, committed, verdict):
    """Checks: a missing seal is adopted only when the register equals its committed HEAD version, line ends aside. E1."""
    assert register.seal_verdict(seal, working, committed) == verdict


def _tree(base: Path, name: str, *, profile: bool, git: bool) -> Path:
    folder = base / name
    folder.mkdir(parents=True)
    if profile:
        (folder / "mkway").mkdir()
        (folder / "mkway" / "profile.json").write_text("{}\n", encoding="utf-8")
    if git:
        (folder / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")  # a linked worktree's marker file
    return folder


@pytest.mark.parametrize("case", [
    "the folder is the named root",
    "the folder is below the named root",
    "the folder is in another root",
    "the folder is below another root",
    "the folder is in a git tree with no mkway root",
    "the folder is in no git tree and no mkway root",
])
def test_the_cli_root_choice_table(tmp_path, case):
    """Checks: the cli root is the named root, or the other mkway root that holds the current folder. E2."""
    main = _tree(tmp_path, "main", profile=True, git=True)
    copy = _tree(tmp_path, "copy", profile=True, git=True)
    plain = _tree(tmp_path, "plain", profile=False, git=True)
    (main / "src").mkdir()
    (copy / "src" / "deep").mkdir(parents=True)
    (plain / "src").mkdir()
    loose = tmp_path / "loose"
    loose.mkdir()
    rows = {
        "the folder is the named root": (main, main, main),
        "the folder is below the named root": (main, main / "src", main),
        "the folder is in another root": (main, copy, copy),
        "the folder is below another root": (main, copy / "src" / "deep", copy),
        "the folder is in a git tree with no mkway root": (main, plain / "src", main),
        "the folder is in no git tree and no mkway root": (main, loose, main),
    }
    named, here, expected = rows[case]
    assert paths.cli_root(named, here) == expected, case


def test_find_root_trusts_the_variable_for_the_hook_and_asks_the_folder_for_the_cli(tmp_path):
    """Checks: the hook keeps the variable's root whatever the folder, and the CLI lets the folder decide. E2."""
    main = _tree(tmp_path, "main", profile=True, git=True)
    copy = _tree(tmp_path, "copy", profile=True, git=True)
    env = {paths.ROOT_ENV: str(main)}
    assert paths.find_root(env=env, cwd=copy) == main.resolve()
    assert paths.find_root(env=env, cwd=copy, env_needs_cwd=True) == copy.resolve()
    assert paths.find_root(env=env, cwd=main, env_needs_cwd=True) == main.resolve()
    assert paths.find_root(env=env, root_arg=str(main), cwd=copy, env_needs_cwd=True) == main.resolve()


@pytest.mark.engine_repo  # reads the engine repository's own register, changelog and cards
def test_register_changelog_and_card_name_the_card():
    """Checks: the register row, the CHANGELOG line and the card folder name MW-054. E8; VERSION is not changed here."""
    register_text = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    title = "A builder in a git worktree copy can take and work its card"
    assert f"| MW-054 | {title} |" in register_text
    assert (REPO / "cards" / "MW-054-copy-works" / "CARD.md").is_file()
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    holding = [sec.splitlines() for sec in changelog.split("\n## ")[1:] if f"MW-054: {title}" in sec]  # MW144-D2
    assert len(holding) == 1 and holding[0][0].strip().count(".") == 2 and holding[0][0].strip().replace(".", "").isdigit()

"""Card MW-071 (decision: R180), layer shell: the close check finds a configured checker's agent definition on real files
and reads its `tools:` line: first the task root's `.claude/agents/<name>.md`, then the user's folder named by the
environment (HOME and USERPROFILE; the conftest points both at an empty scratch folder). Synthetic names and sessions."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
from _engine import agent_file, task_root  # noqa: E402
from _mw068 import prove  # noqa: E402
import verdicts  # noqa: E402

NODE = "tests/test_a.py::test_one"
FILE = "tests/test_a.py"
NO_FILE = object()  # the root holds no definition of the checker
HEADER = "| Node | Verdict | Reason | By |\n|---|---|---|---|\n"


def _root(tmp_path, checker, agent_tools=NO_FILE):
    """A task root that names `checker` and holds its definition listing `agent_tools` (None: no tools line)."""
    root = task_root(tmp_path, outbox={"checkers": [checker]}, agent_tools=None)
    (root / "tests").mkdir()
    (root / "tests" / "test_a.py").write_text("def test_one():\n    pass\n", encoding="utf-8")
    if agent_tools is not NO_FILE:
        agent_file(root, checker, agent_tools)
    return root


def _problem(root, checker):
    """The close decision for a `true` row by the session s2 with its proof (a fresh reader agent of type `checker` and the
    write record): only the checker's definition decides the answer."""
    folder = root / "tests" / "verdicts"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "CARD-001.md").write_text(HEADER + f"| {NODE} | true | fine | session:s2 |\n", encoding="utf-8")
    prove(root, "CARD-001", FILE, "s2", agent_type=checker)
    return verdicts.problem(root, "CARD-001", [NODE], "", root / "mkway" / "state", [checker])


def test_a_task_with_a_read_only_fresh_reader_passes_the_close_check(tmp_path):
    """Checks: a read-only fresh reader passes the close check, the nearest allow of the Bash refusal, where only the definition differs."""
    root = _root(tmp_path, "fresh-reader", "Read, Grep")
    assert _problem(root, "fresh-reader") is None


def test_a_task_whose_checker_has_bash_is_refused_at_the_close_check(tmp_path):
    """Catches: the old critic type (it has Bash) accepted as the blind checker because its agent file is never read."""
    root = _root(tmp_path, "critic", "Read, Grep, Bash")
    problem = _problem(root, "critic")
    assert problem is not None
    assert problem[0] == "checker-not-read-only"
    assert "critic" in problem[1]
    assert "Bash" in problem[1]


def test_a_definition_only_in_the_user_folder_is_found_through_the_environment(tmp_path, user_home):
    """Checks: a checker defined only in the user's folder is found through the environment, not reported not found."""
    root = _root(tmp_path, "fresh-reader")
    agent_file(user_home, "fresh-reader", "Read, Grep")
    assert _problem(root, "fresh-reader") is None


def test_the_task_definition_is_read_before_the_user_definition(tmp_path, user_home):
    """Checks: the task's own definition is read before the user's, so a read-only task type is judged by its own file."""
    root = _root(tmp_path, "fresh-reader", "Read, Grep")
    agent_file(user_home, "fresh-reader", "Read, Grep, Bash")
    assert _problem(root, "fresh-reader") is None


def test_no_agent_file_in_either_folder_is_refused_and_names_both_paths(tmp_path, user_home):
    """Catches: a checker with no definition anywhere accepted, or refused without saying where the engine looked."""
    root = _root(tmp_path, "fresh-reader")
    problem = _problem(root, "fresh-reader")
    assert problem is not None
    assert problem[0] == "checker-not-found"
    assert str(root / ".claude" / "agents" / "fresh-reader.md") in problem[1]
    assert str(user_home / ".claude" / "agents" / "fresh-reader.md") in problem[1]


def test_an_agent_file_with_no_tools_line_is_refused_as_not_read_only(tmp_path):
    """Catches: a definition with no `tools:` line (it has every tool) read as having none, so it passes."""
    root = _root(tmp_path, "fresh-reader", None)
    problem = _problem(root, "fresh-reader")
    assert problem is not None
    assert problem[0] == "checker-not-read-only"

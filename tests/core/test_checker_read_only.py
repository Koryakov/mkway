"""Card MW-071 (decision: R180), layer core: the decision on a configured checker's agent definition, as a table. No disk,
no git, no clock. A `Checker` fact is the name, the tools its definition lists (None: no tools line) and the found flag.
Each expected value is written from the ruling, never from `decide`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: `_engine` puts engine/ on the path
import _engine  # noqa: E402,F401
from core_verdicts import Checker, Facts, Row, decide  # noqa: E402

NODE = "tests/test_a.py::test_one"
ROW = Row(NODE, "true", "one clause, one case", "session:reader")
SEARCHED = "T/.claude/agents/fresh-reader.md and H/.claude/agents/fresh-reader.md"


def facts(*checkers, nodes=(NODE,)):
    """A card that names one node, a `true` row by a reader who is not the holder, and the given checker facts."""
    return Facts(nodes=tuple(nodes), rows=(ROW,), authors={}, holder="session:holder", checkers=tuple(checkers))


def reader(tools=("Read", "Grep"), found=True, name="fresh-reader"):
    return Checker(name, tools, found, SEARCHED)


def reasons(verdict):
    return [r.reason for r in verdict.refusals]


def test_a_checker_that_lists_read_and_grep_is_allowed():
    """Checks: the nearest allow of the Bash deny: the same checker without the extra tool."""
    assert decide(facts(reader(("Read", "Grep")))).allowed


def test_a_checker_that_lists_read_only_is_allowed():
    """Checks: the nearest allow of the missing-tools-line deny: one tool of the two, Read."""
    assert decide(facts(reader(("Read",)))).allowed


def test_a_checker_that_lists_bash_is_refused_as_not_read_only():
    """Catches: a reader with a shell (the old critic) accepted as the blind checker, so it can run code and edit files."""
    verdict = decide(facts(reader(("Read", "Grep", "Bash"))))
    assert not verdict.allowed
    assert reasons(verdict) == ["checker-not-read-only"]


def test_a_checker_with_no_tools_line_is_refused_as_not_read_only():
    """Catches: a definition with no tools line (it then has every tool) accepted as read-only."""
    verdict = decide(facts(reader(None)))
    assert not verdict.allowed
    assert reasons(verdict) == ["checker-not-read-only"]


def test_a_checker_with_no_agent_file_is_refused_as_not_found():
    """Catches: a checker name with no agent definition anywhere accepted, so nobody knows what it can do."""
    verdict = decide(facts(reader(None, found=False)))
    assert not verdict.allowed
    assert reasons(verdict) == ["checker-not-found"]


def test_the_not_read_only_text_names_the_checker_and_the_extra_tool():
    """Catches: a refusal that does not say which checker failed or which tool it lists beyond Read and Grep."""
    text = decide(facts(reader(("Read", "Bash"), name="critic"))).refusals[0].text
    assert "critic" in text
    assert "Bash" in text


def test_the_not_found_text_names_the_checker_and_the_paths_searched():
    """Catches: a not-found refusal that hides where the engine looked, so the owner cannot place the file."""
    text = decide(facts(reader(None, found=False))).refusals[0].text
    assert "fresh-reader" in text
    assert SEARCHED in text


def test_one_checker_that_is_not_read_only_refuses_among_good_ones():
    """Catches: only the first configured checker judged, so a later one with a shell passes."""
    verdict = decide(facts(reader(), reader(("Read", "Bash"), name="critic")))
    assert reasons(verdict) == ["checker-not-read-only"]
    assert "critic" in verdict.refusals[0].text


def test_a_card_naming_no_node_is_not_refused_for_its_checker():
    """Catches: a card with no test node (every row `checked by reading`) refused for a checker it never uses."""
    assert decide(facts(reader(("Read", "Bash")), nodes=())).allowed

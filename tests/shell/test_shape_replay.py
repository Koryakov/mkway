"""Card MW-073 (decision: R177), the replay: a test that reads the text of other test files by path through a loop, the shape of
a real test of this repository that a tests-only commit let in with no shape check. The case is the synthetic fixture
`fixtures/synthetic/shape/reads_other_test_files.txt`, committed through the gate as a new test file."""
import _engine  # noqa: F401
from _commit_project import make_project, stage
from _engine import FIXTURES, gate_call
import gate_test_shape

TARGET = "tests/test_replay.py"
CASE = FIXTURES / "shape" / "reads_other_test_files.txt"


def test_the_replay_of_a_test_that_reads_other_test_files_is_refused(tmp_path):
    """Catches: a tests-only commit that adds a test reading other test files through a loop, with no check of its shape."""
    root = make_project(tmp_path)
    stage(root, TARGET, CASE.read_text(encoding="utf-8"))
    verdict = gate_call(gate_test_shape.check, root, tool="Bash", tool_input={"command": "git commit -m x"},
                        gate="tests.shape")
    assert (verdict.kind, verdict.reason_id) == ("refuse", "test-shape")
    assert "tests/test_replay.py::test_the_listed_tests_are_marked: S1" in verdict.message
    assert "tests/test_replay.py::test_the_listed_tests_are_marked: S4" in verdict.message
    assert "tests/test_replay.py::test_the_listed_tests_are_marked: S5" in verdict.message

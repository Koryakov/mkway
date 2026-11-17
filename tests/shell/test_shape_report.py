"""Card MW-073 (decision: R177): the one-off report that lists every existing test function that breaks S1 to S7, per rule and
per file, for the later re-judging card. Synthetic files in a scratch folder."""
import subprocess
import sys

import _engine  # noqa: F401
from _engine import ENGINE
import shape_report

A_FILE = "tests/test_a.py"
B_FILE = "tests/core/test_b.py"
FILES = {
    A_FILE: 'def test_loop():\n    for x in (1,):\n        assert x\n\n\n'
                       'def test_ok():\n    """Checks: x."""\n    assert 1 == 1\n',
    B_FILE: 'def test_c():\n    """Catches: x."""\n    assert f(1) == f(1)\n',
    "tests/helpers.py": "def test_not_a_test_file():\n    pass\n",
}


def _tree(tmp_path):
    for rel, text in FILES.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def test_the_report_counts_the_breaks_per_rule_and_per_file(tmp_path):
    """Checks: three test functions are judged, two break a rule once or twice, counted per rule and per file."""
    report = shape_report.scan(_tree(tmp_path), "tests")
    assert report.tests == 3
    assert report.by_rule == {"S1": 1, "S4": 1, "S7": 1}
    assert report.by_file == {A_FILE: 2, B_FILE: 1}


def test_the_report_command_prints_a_line_per_rule_and_per_file(tmp_path):
    """Checks: the command prints the count of judged tests, then one `<rule>: <n>` and one `<file>: <n>` line."""
    proc = subprocess.run([sys.executable, str(ENGINE / "shape_report.py"), "tests"], cwd=str(_tree(tmp_path)),
                          capture_output=True, text=True, timeout=20)
    lines = proc.stdout.splitlines()
    assert proc.returncode == 0
    assert "tests judged: 3" in lines
    assert "S1: 1" in lines
    assert "tests/test_a.py: 2" in lines

"""Card MW-114: the way out of `red-ids-still-red` for a recorded red test whose parameters are raw strings with spaces (the
case of DD-013, rebuilt with made-up strings), on a real small git repository with real pytest. The setup is copied from
`tests/shell/test_red_facts.py` (its `red_commit`) and `tests/_red_project.py`. To keep each test well under the shell limit
the red-first commit (a gate run and a commit, the costly part of the setup) is made once per worker in a template folder
(MW-085) and each test gets a copy; only the code commit, which is what the test judges, runs in the test. Synthetic files
only."""
import pytest  # noqa: F401

import _template
from _commit_project import git, reason, run_gate, stage
from _red_project import recorded, red_project

SQL_FILE = "tests/test_sql.py"
SQL_RED = '''import app
import pytest

CASES = ["select * from t where a = 1", "drop table x; --", "insert into t values (1, 'a')"]


@pytest.mark.parametrize("sql", CASES)
def test_sql(sql):
    """Catches: clean is missing."""
    assert app.clean(sql) == sql
'''
SQL_SKIPPED = SQL_RED.replace("    assert app", '    pytest.skip("x")\n    assert app')
APP_CLEAN = "def add(a, b):\n    return a + b\n\n\ndef clean(text):\n    return text\n"
TEMPLATE = "mw114_red_sql"


def build_red_sql(folder):
    """The project of `tests/_red_project.py` with the tests-only commit of the parametrized red test made: allowed by the gate,
    and the test recorded as red by its id without the cases."""
    root = red_project(folder)
    stage(root, SQL_FILE, SQL_RED)
    assert reason(run_gate(root)) == "allow"
    git(root, "commit", "-q", "-m", "CARD-001 red")
    assert recorded(root) == [f"{SQL_FILE}::test_sql"]
    return root


@pytest.fixture
def sql_project(tmp_path, template_copy):
    """A copy of the template (built once per worker) in this test's own tmp_path; built in tmp_path when a copy cannot be made."""
    try:
        return template_copy(TEMPLATE, build_red_sql) / "red"
    except _template.TemplateHoldsItsPath:
        return build_red_sql(tmp_path)


def test_a_recorded_red_test_with_raw_sql_strings_that_now_passes_is_judged_passed(sql_project):
    """Catches: a recorded red test with spaces in its parameters counted as gone once it passes (DD-013)."""
    stage(sql_project, "app.py", APP_CLEAN)
    assert reason(run_gate(sql_project)) == "allow"


def test_a_recorded_red_test_with_raw_sql_strings_that_is_skipped_is_refused_as_skipped(sql_project):
    """Catches: a skipped recorded test let through, or refused with the wrong words (deleted or renamed)."""
    stage(sql_project, SQL_FILE, SQL_SKIPPED)
    stage(sql_project, "app.py", APP_CLEAN)
    verdict = run_gate(sql_project)
    assert reason(verdict) == "red-ids-still-red"
    assert "it is skipped" in verdict.message

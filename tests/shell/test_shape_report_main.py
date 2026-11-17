"""Card MW-073 (decision: R177): the report's `main` in this process, on a synthetic folder: the default folder and a named one."""
import _engine  # noqa: F401
import shape_report

BAD = "def test_loop():\n    for x in (1,):\n        assert x\n"


def _tree(tmp_path):
    path = tmp_path / "tests" / "test_a.py"
    path.parent.mkdir()
    path.write_text(BAD, encoding="utf-8")
    return tmp_path


def test_the_report_main_reads_the_tests_folder_by_default(tmp_path, monkeypatch, capsys):
    """Checks: with no argument the report judges `tests` under the current folder and exits 0."""
    monkeypatch.chdir(_tree(tmp_path))
    assert shape_report.main([]) == 0
    assert "S1: 1" in capsys.readouterr().out.splitlines()


def test_the_report_main_reads_the_folder_it_is_given(tmp_path, monkeypatch, capsys):
    """Checks: a named folder is judged, and a folder with no test file reports zero tests."""
    monkeypatch.chdir(_tree(tmp_path))
    assert shape_report.main(["empty"]) == 0
    assert "tests judged: 0" in capsys.readouterr().out.splitlines()

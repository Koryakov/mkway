"""Card MW-102 (decision: R254), layer shell: the commit gate on a real small git repository whose card CARD-001 is ordered
by the session `lead`. The rows of the verdict file are judged from the content the commit takes (the staged blob for a plain
commit, the working file for the `-- <paths>` form) by the close's row proof. Rows are written by the real `verdict add` (in
process) or typed by hand. Synthetic names only."""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
import _mw102 as v  # noqa: E402
import runner  # noqa: E402


def test_an_edited_row_staged_with_a_clean_working_copy_is_unproven(tmp_path):
    """Catches: a row edited by hand after `verdict add` and committed, judged by a file other than the staged one."""
    root = v.verdict_root(tmp_path)
    v.add(root, v.N1)
    v.put(root, v.text(root).replace("one clause, one case", v.EDITED))
    v.stage(root)
    reason, text = v.decide(root)
    assert (reason, v.N1 in text) == ("verdict-unproven", True)


def test_a_clean_row_staged_with_an_edited_working_copy_is_allowed(tmp_path):
    """Checks: the nearest allow of the staged-row case: the staged row is the real one, the working file differs and is not what the commit takes."""
    root = v.verdict_root(tmp_path)
    v.add(root, v.N1)
    v.stage(root)
    v.put(root, v.text(root).replace("one clause, one case", v.EDITED))
    assert v.decide(root) == ("allow", "")


def test_the_paths_form_judges_the_working_file(tmp_path):
    """Catches: the `-- <paths>` form judged by the staged blob while git commits the working file."""
    root = v.verdict_root(tmp_path)
    v.add(root, v.N1)
    v.save(root)
    v.put(root, v.text(root).replace("one clause, one case", v.EDITED))
    reason, text = v.decide(root, v.NAMED)
    assert (reason, v.N1 in text) == ("verdict-unproven", True)


def test_the_paths_form_with_a_row_written_by_the_command_is_allowed(tmp_path):
    """Checks: the nearest allow of the paths-form case: a second row written by the command after the first was committed."""
    root = v.verdict_root(tmp_path)
    v.add(root, v.N1)
    v.save(root)
    v.add(root, v.N2)
    assert v.decide(root, v.NAMED) == ("allow", "")


def test_a_typed_row_with_no_record_is_unproven(tmp_path):
    """Catches: a verdict row typed by hand, with no `verdict add` record behind it, committed by the orderer."""
    root = v.verdict_root(tmp_path)
    v.typed(root, v.N1)
    v.stage(root)
    reason, text = v.decide(root)
    assert (reason, v.N1 in text) == ("verdict-unproven", True)


def test_rows_written_by_verdict_add_are_allowed(tmp_path):
    """Checks: rows of two nodes written through the real `verdict add` are committed by the orderer."""
    root = v.verdict_root(tmp_path)
    v.add(root, v.N1, v.N2)
    v.stage(root)
    assert v.decide(root) == ("allow", "")


def test_a_row_for_a_node_no_acceptance_row_names_is_not_judged(tmp_path):
    """Checks: a typed row of a node no Acceptance row of the card names is left to the close, as the close leaves it; the real row beside it is proved."""
    root = v.verdict_root(tmp_path)
    v.add(root, v.N1)
    v.put(root, v.text(root) + f"| tests/test_zzz.py::test_none | true | typed by hand | session:{v.READER} |\n")
    v.stage(root)
    assert v.decide(root) == ("allow", "")


def test_with_no_checkers_the_proof_is_skipped(tmp_path):
    """Checks: a profile with no `outbox.checkers` skips the row proof as the close does (R179): a typed row is committed."""
    root = v.verdict_root(tmp_path, checkers=())
    v.typed(root, v.N1)
    v.stage(root)
    assert v.decide(root) == ("allow", "")


def test_with_cards_verdicts_off_the_proof_is_skipped(tmp_path):
    """Checks: `cards.verdicts: off` skips the row proof as the close does: a typed row is committed."""
    root = v.verdict_root(tmp_path, verdicts_off=True)
    v.typed(root, v.N1)
    v.stage(root)
    assert v.decide(root) == ("allow", "")


def test_a_staged_blob_git_cannot_show_refuses_unreadable(tmp_path, monkeypatch):
    """Catches: a staged verdict file whose blob git cannot show, read as an empty file and allowed."""
    root = v.verdict_root(tmp_path)
    v.typed(root, v.N1)
    v.stage(root)
    real = runner.git

    def failing(cwd, *args, **kw):
        if args and args[0] == "show":
            return subprocess.CompletedProcess(args, 128, "", "fatal: cannot show")
        return real(cwd, *args, **kw)
    monkeypatch.setattr(runner, "git", failing)
    assert v.decide(root)[0] == "commit-unreadable"

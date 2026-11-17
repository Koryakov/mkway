"""Card MW-074 (decision: R177), rows E1 to E10: the hermetic guard of tests/core. The autouse fixture of
tests/core/conftest.py is already on for every test in this file; a call it forbids raises `HermeticError`."""
import os
import re
import subprocess

import pytest

from _hermetic import HermeticError
from _mw098_guard import open_socket, sleep_zero

TEXT = "hermetic test: {} is not allowed in tests/core"


@pytest.mark.parametrize("name", ["run", "Popen", "call", "check_call", "check_output"])
def test_a_subprocess_call_is_refused(name):
    """Catches: a core test that starts a process."""
    with pytest.raises(HermeticError, match=re.escape(TEXT.format("subprocess." + name))):
        getattr(subprocess, name)(["x"])


def test_a_subprocess_helper_that_starts_nothing_is_allowed():
    """Checks: the subprocess module itself stays usable; only the calls that start a process are refused."""
    assert subprocess.list2cmdline(["a", "b"]) == "a b"


def test_a_socket_is_refused():
    """Catches: a core test that opens a network socket."""
    with pytest.raises(HermeticError, match=re.escape(TEXT.format("socket.socket"))):
        open_socket()


def test_a_sleep_is_refused():
    """Catches: a core test that waits on the clock."""
    with pytest.raises(HermeticError, match=re.escape(TEXT.format("time.sleep"))):
        sleep_zero()


@pytest.mark.parametrize("mode", ["w", "a", "x"])
def test_an_open_for_write_outside_tmp_path_is_refused(tmp_path, mode):
    """Catches: a core test that writes a file outside its own tmp_path."""
    with pytest.raises(HermeticError, match=r"file write outside tmp_path \(.*outside\.txt\) is not allowed in tests/core"):
        open(tmp_path.parent / "outside.txt", mode)


def test_a_path_write_text_outside_tmp_path_is_refused(tmp_path):
    """Catches: a core test that writes through pathlib outside its own tmp_path."""
    with pytest.raises(HermeticError, match=r"file write outside tmp_path \(.*outside\.txt\) is not allowed in tests/core"):
        (tmp_path.parent / "outside.txt").write_text("x", encoding="utf-8")


def test_a_write_inside_tmp_path_is_allowed(tmp_path):
    """Checks: a file written and read back inside the test's own tmp_path."""
    target = tmp_path / "inside.txt"
    target.write_text("kept", encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "kept"


def test_a_read_outside_tmp_path_is_allowed():
    """Checks: reading a file outside tmp_path is not a write and is allowed."""
    with open(os.devnull, encoding="utf-8") as handle:
        assert handle.read(3) == ""


def test_a_write_through_a_descriptor_is_allowed(tmp_path):
    """Checks: a file opened by descriptor number is not a path write, so the guard leaves it alone."""
    fd = os.open(tmp_path / "fd.txt", os.O_WRONLY | os.O_CREAT)
    with open(fd, "w", encoding="utf-8") as handle:
        handle.write("ok")
    assert (tmp_path / "fd.txt").read_text(encoding="utf-8") == "ok"


def test_the_refusal_text_has_the_fixed_form():
    """Catches: a refusal text that does not name the call in the fixed form."""
    with pytest.raises(HermeticError) as caught:
        sleep_zero()
    assert str(caught.value) == "hermetic test: time.sleep is not allowed in tests/core"

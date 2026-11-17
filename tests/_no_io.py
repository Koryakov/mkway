"""The no-disk guard shared by the core decide tests (card MW-087, decision R215). A helper, not a test file.

`no_io()` makes any file, process or clock access inside its block raise AssertionError. It patches the union of the
calls the three core decide test files used to guard on their own.

The tracer's own I/O is not the core's: when the suite runs under coverage, the tracer opens its first look at a source
file (a real path lookup) from inside the guarded block, and that call is not the code under test. A call passes through
to the original when the call stack, between the call and the line that entered the block, holds a frame of the
`coverage` package. Nothing wider: a frame of engine/ is on the stack for the whole call, so no other criterion
separates the tracer from the code under test. Frames below the line that entered the block never count.
"""
import builtins
import contextlib
import io
import os
import pathlib
import subprocess
import sys
import time

import pytest

PATCHED = ((builtins, "open"), (io, "open"), (os, "stat"), (os, "lstat"), (os, "scandir"), (os, "listdir"),
           (os, "getcwd"), (subprocess, "Popen"), (time, "time"), (time, "monotonic"), (time, "perf_counter"),
           (pathlib.Path, "stat"), (pathlib.Path, "exists"), (pathlib.Path, "is_file"), (pathlib.Path, "is_dir"),
           (pathlib.Path, "read_text"), (pathlib.Path, "resolve"))


def _is_coverage(frame):
    name = frame.f_globals.get("__name__") or ""
    return name == "coverage" or name.startswith("coverage.")


@contextlib.contextmanager
def no_io():
    """Any disk, process or clock access inside the block fails the test; the tracer's own I/O is not the core's (R215)."""
    entry = sys._getframe(2)  # 0 this generator, 1 contextlib __enter__, 2 the line that entered the block
    originals = {(owner, name): getattr(owner, name) for owner, name in PATCHED}

    def make_boom(original):
        def boom(*a, **k):
            frame = sys._getframe(1)
            while frame is not None and frame is not entry:
                if _is_coverage(frame):
                    return original(*a, **k)
                frame = frame.f_back
            raise AssertionError("the core touched the disk, a process or the clock")
        return boom

    with pytest.MonkeyPatch.context() as mp:
        for (owner, name), original in originals.items():
            mp.setattr(owner, name, make_boom(original))
        yield

"""Root launcher: runs engine/mkway.py.

It exists so that the command path is the same in the engine repository and in a task's copy: the copy keeps the
repository tree under `<bundle.root>/engine/`, so every hook entry and every document says
`mkway/engine/mkway.py` (decision C12). It is part of the fixed file set and of the copy's hash.

For `hook`, a failure before the dispatcher runs (an engine module that cannot be imported, a command line the
parser refuses, any other non-zero exit) follows the group rule of R13c (fix check N6): one
`mkway dispatcher-error: <class> at start-up` stderr line, exit 2 in `edit` and `shell`, else exit 0.
"""
import json
import runpy
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent / "engine"  # the engine's own code beside this file; never the task root
BLOCKING_GROUPS = ("edit", "shell")  # = engine/dispatch.py BLOCKING_GROUPS (test E54)


def _group(argv):
    for i, arg in enumerate(argv):
        if arg == "--group" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--group="):
            return arg.split("=", 1)[1]
    return None


def _start_up_failure(cls: str, group) -> int:
    blocking = group in BLOCKING_GROUPS
    line = (f"mkway dispatcher-error: {cls} at start-up; "
            + ("the tool call is blocked, because the dispatcher could not start. This is not a rule breach; "
               "report it." if blocking else "nothing was blocked."))
    sys.stderr.write(line + "\n")
    if not blocking:
        sys.stdout.write(json.dumps({"systemMessage": line}))
    return 2 if blocking else 0


def main() -> None:
    sys.path.insert(0, str(ENGINE))
    hook = sys.argv[1:2] == ["hook"]
    try:
        runpy.run_path(str(ENGINE / "mkway.py"), run_name="__main__")
    except SystemExit as exc:
        code = exc.code
        if not hook or code in (0, None) or (code == 2 and _group(sys.argv) in BLOCKING_GROUPS):
            raise
        sys.exit(_start_up_failure("SystemExit", _group(sys.argv)))
    except KeyboardInterrupt:
        raise
    except BaseException as exc:
        if not hook:
            raise
        sys.exit(_start_up_failure(exc.__class__.__name__, _group(sys.argv)))


main()

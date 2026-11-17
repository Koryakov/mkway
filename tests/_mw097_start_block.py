"""Start-block helpers for the start-line tests of card MW-097: the functions that render a task root's start block
and read its `gates on:` and `gates off:` lines. Copied from the start-block helpers of tests/test_mw007_start_block.py
so that no test module imports another test module (S5)."""
import json

import _engine  # noqa: F401  (puts engine/ on the path for startline)
import startline

ENV = {"CLAUDECODE": "1"}


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _set_gates(root, gates):
    profile = _profile(root)
    profile["gates"] = gates
    (root / "mkway" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    return profile


def _block(root, manifest, profile=None, errors=None):
    return startline.render(root, root / "mkway" / "profile.json", profile if profile is not None else _profile(root),
                            errors or [], manifest, ENV, session="s1")


def _line(block, prefix):
    (line,) = [x for x in block.splitlines() if x.startswith(prefix)]
    return line


def _names(line):
    return [n.strip() for n in line.split(":", 1)[1].split(";")[0].split(",") if n.strip() and n.strip() != "none"]

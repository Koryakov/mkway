"""The README section «Tests before a commit» and the start block's line for the gate (card MW-005, part C)."""
import json
import re

import pytest

from _engine import REPO, task_root
import dispatch
import startline

README = REPO / "README.md"
HEADING = "## Tests before a commit"


def _text():
    return README.read_text(encoding="utf-8")


def _section():
    text = _text()
    start = text.index(HEADING + "\n")
    rest = text[start + len(HEADING):]
    nxt = re.search(r"^## ", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


def _flat(text):
    return " ".join(text.split())


@pytest.mark.engine_repo  # the README is not in an engine copy: `mkway check` leaves these out
def test_the_readme_has_one_section_tests_before_a_commit():
    """E19 (part C): one heading `## Tests before a commit`, with a body, placed before «Known limits», and no other
    heading about tests before a commit.
    Catches: a second section, a heading with no text, a section hidden after the limits."""
    text = _text()
    assert text.count("\n" + HEADING + "\n") == 1
    assert len(_flat(_section())) > 600
    assert text.index(HEADING) < text.index("## Known limits")
    assert len([h for h in re.findall(r"^## .*$", text, re.M) if "tests" in h.lower() and "commit" in h.lower()]) == 1


@pytest.mark.engine_repo
def test_the_section_states_the_rules_the_keys_and_every_reason():
    """E20 (part C): the section names the gate and its group, the staged tree and how it is exported, the red-first
    rule, the docs-only rule, the budget with its default, the one run per staged tree and the state file, the
    environment rule, the owner's terminal, every reason id of the manifest entry and every key with its default.
    Reason ids and keys are read from the manifest and the schema, so the text cannot drift from the gate.
    Catches: a section that leaves out a refusal a session will meet, or a key with no default written down."""
    flat = _flat(_section())
    manifest = json.loads((REPO / "engine" / "manifest.json").read_text(encoding="utf-8"))["entries"]
    (entry,) = [e for e in manifest if e["name"] == "commit_tests"]
    assert len(entry["reason_ids"]) == 23  # changed by MW-134 (R347, R348): the seven retire ids; MW-056 (E15): the warn `commit-tests-still-red` is the fifth id; MW-072: four red proof ids; MW-090 (T7 decision: R225): five case_map ids; MW-131 (R322): the partial-find warn
    for reason in entry["reason_ids"]:
        assert f"`{reason}`" in flat, reason
    schema = json.loads((REPO / "engine" / "profile.schema.json").read_text(encoding="utf-8"))
    for key in schema["properties"]["tests"]["properties"]:
        assert f"`tests.{key}`" in flat, key
    for needed in ("`commit_tests`", "`git checkout-index -a -f --prefix`", "the staged tree", "red-first",
                   "`test_roots`", "`paths.docs`", "`test_env`", "`ENGINE_TERMS_FILE`", "`python -m pytest -q`",
                   "`gates.commit_tests.budget_seconds`", "`780`", "`commit_tests.jsonl`", "`gates.commit_tests`",
                   "`gates off:`", "no hook runs"):
        assert needed in flat, needed
    # changed by MW-072 (R177): a tests-only commit of a session with a card and pytest runs the suite, so the sentence says when
    for sentence in ("otherwise it may be red and runs no tests.",
                     "A commit whose staged files all match `paths.docs` runs no tests.",
                     "The owner's own terminal is not gated: no hook runs there."):
        assert sentence in flat, sentence


def test_the_start_block_lists_the_gate_by_its_manifest_name(tmp_path):
    """E21 (part C): with the real manifest the line `gates on:` names `commit_tests` after `lock.shell`; with
    `gates.commit_tests.on: false` the line `gates off:` names it and `gates on:` does not.
    Catches: a gate that can be switched off with nothing on the start block saying so."""
    manifest = dispatch.load_manifest(dispatch.ENGINE_DIR)
    root = task_root(tmp_path)
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))

    def line(prefix, prof):
        block = startline.render(root, root / "mkway" / "profile.json", prof, [], manifest, {"CLAUDECODE": "1"},
                                 session="s1")
        (found,) = [x for x in block.splitlines() if x.startswith(prefix)]
        return [n.strip() for n in found.split(":", 1)[1].split(";")[0].split(",") if n.strip() != "none"]

    on = line("gates on:", profile)
    # changed by the port onto MW-006: `commit_files` (the cheap file checks) sits between `lock.shell` and the slow
    # test run `commit_tests`, so the gate is after the lock gate and after `commit_files`, not directly after it
    assert "commit_tests" in on and on.index("lock.shell") < on.index("commit_files") < on.index("commit_tests")
    assert line("gates off:", profile) == []
    off_profile = dict(profile, gates={"commit_tests": {"on": False}})
    assert line("gates off:", off_profile) == ["commit_tests"]
    assert "commit_tests" not in line("gates on:", off_profile)

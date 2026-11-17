"""Rule cards paired with tests (card MW-021): the settings, the card list, and the last green tree of a card's test.

Two profile keys, both with no default, so the check is off until a branch sets them:
- `rules.cards`: globs of the rule-card files; the id of a card is read from its file name by the form
  `ids.rule_card` (the whole name without its extension, else the part before the first `-`, `_`, `.` or space);
- `rules.test_for`: the path of a card's test, with `{id}` for the card id.

The commit gate (`gate_commit`) refuses a commit that adds or changes a card and does not stage its test; the
`mkway rules` command and the start block line read the list here. No task name and no natural-language word is in
this file: the globs, the id form and the test path all come from the profile.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import gate_commit_tests
import helpers
import profiles
import runner

STATE_FILE = "commit_tests.jsonl"  # the rows of the gate `commit_tests` (MW-005)
SCAN_ROWS = 50  # newest green rows looked at for the last green tree of one test
SKIP_FOLDERS = {".git", "__pycache__", ".pytest_tmp", ".pytest_cache", "node_modules"}
NOT_SET = ("rules: not set; add `rules.cards` (globs of the rule-card files) and `rules.test_for` (a test path "
           "with `{id}`) to the profile")


def settings(profile) -> dict:
    """`cards` (a non-empty list of non-empty strings, else `[]`) and `test_for` (a string that holds `{id}`, else
    None). A missing or unusable value takes its default, so a gate never fails on a bad key."""
    raw = profile.get("rules") if isinstance(profile, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    cards = raw.get("cards")
    if not isinstance(cards, list) or not cards or any(not isinstance(c, str) or not c for c in cards):
        cards = []
    test_for = raw.get("test_for")
    if not isinstance(test_for, str) or "{id}" not in test_for:
        test_for = None
    return {"cards": list(cards), "test_for": test_for}


def active(profile) -> bool:
    """True when both keys are usable. Without a usable `ids.rule_card` no file name holds an id, so no file is a rule
    card and nothing is refused."""
    cfg = settings(profile)
    return bool(cfg["cards"] and cfg["test_for"])


def _form(profile):
    ids = profile.get("ids") if isinstance(profile, dict) else None
    pattern = ids.get("rule_card") if isinstance(ids, dict) else None
    if not isinstance(pattern, str) or not pattern:
        return None
    try:
        return re.compile(pattern)
    except re.error:
        return None


def card_id(profile, rel: str):
    """The id read from the file name of `rel` by `ids.rule_card`, or None (no form, or no id in the name)."""
    form = _form(profile)
    if form is None:
        return None
    name = rel.replace("\\", "/").rsplit("/", 1)[-1]
    stem = name.rsplit(".", 1)[0] if "." in name else name
    for candidate in (stem, re.split(r"[-_. ]", stem, maxsplit=1)[0]):
        if candidate and form.fullmatch(candidate):
            return candidate
    return None


def is_card(profile, rel: str):
    """The id of `rel` when it is a rule card (it matches a `rules.cards` glob and its name holds an id), else None.
    None as well when the check is off."""
    if not active(profile):
        return None
    if not any(helpers.matches(rel, glob) for glob in settings(profile)["cards"]):
        return None
    return card_id(profile, rel)


def test_path(profile, ident: str):
    """The test path of card `ident`, from `rules.test_for`."""
    return settings(profile)["test_for"].replace("{id}", ident)


def cards(root, profile) -> list:
    """[(id, card path, test path, test exists)] of the rule cards in the working tree, by card path. A file that
    matches the globs but holds no id in its name is not a rule card."""
    if not active(profile):
        return []
    root = Path(root)
    state = profiles.state_dir(root, profile).resolve()
    found = []
    for folder, names, files in os.walk(root):
        names[:] = [n for n in names if n not in SKIP_FOLDERS and (Path(folder) / n).resolve() != state]
        for name in files:
            rel = (Path(folder) / name).relative_to(root).as_posix()
            ident = is_card(profile, rel)
            if ident:
                test = test_path(profile, ident)
                found.append((ident, rel, test, (root / test).is_file()))
    return sorted(found, key=lambda row: (row[1], row[0]))


def last_green_tree(root, profile, test: str, cache=None):
    """The git tree id of the newest `pass` row of `commit_tests.jsonl` whose tree holds the file `test`, or None. The
    row's key may be a git tree id or the digest the commit gate writes (`gate_commit_tests.tree_keys`, MW-023); the
    result is the git tree id either way. Only the newest SCAN_ROWS green rows are looked at; a tree git no longer
    has counts as not holding the file. `cache` (a dict) shares the key lookup between calls."""
    try:
        lines = (profiles.state_dir(root, profile) / STATE_FILE).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    green = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("result") == "pass" and isinstance(row.get("tree"), str):
            green.append(row["tree"])
    keys = list(reversed(green[-SCAN_ROWS:]))
    # MW-023: a key is a git tree id or the digest the commit gate writes; one helper maps it to the git tree id
    if cache is None:
        cache = {}
    if None not in cache:  # read once per `mkway rules`, not once per card
        cache.update(gate_commit_tests.trees_of_keys(root, keys))
        cache[None] = None
    named = cache
    prefix = helpers.top_prefix(root)  # MW-140: a tree is the tree of the git TOP; the test path is the root's, so it sits below the prefix
    where = f"{prefix}/{test}" if prefix else test
    for key in keys:
        tree = named.get(key, key)
        try:
            if runner.git(root, "cat-file", "-e", f"{tree}:{where}").returncode == 0:
                return tree
        except (OSError, runner.TimeoutExpired, ValueError, runner.Refused):
            return None
    return None


def lines(root, profile) -> list:
    """The lines of `mkway rules`: one per card, or the one line that names the keys to set."""
    if not active(profile):
        return [NOT_SET]
    out = []
    cache = {}
    for ident, card, test, exists in cards(root, profile):
        tree = last_green_tree(root, profile, test, cache) if exists else None
        out.append(f"{ident}  {card}  {test}  {'exists' if exists else 'missing'}  last green tree "
                   f"{tree[:8] if tree else 'none'}")
    return out or ["rules: no rule card found under `rules.cards`"]


def start_line(root, profile):
    """`rules: N cards, M without tests`, or None when the check is off."""
    if not active(profile):
        return None
    found = cards(root, profile)
    return f"rules: {len(found)} cards, {sum(1 for row in found if not row[3])} without tests"

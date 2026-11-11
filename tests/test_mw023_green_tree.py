"""Card MW-023: one tree key for green test rows. Synthetic task roots only.

The commit gate writes the `tree` of a `commit_tests.jsonl` row as the sha256 of `git ls-files -s -z`; the readers
(`mkway rules`, `mkway built`) must name the same commit by that key or by the git tree id, through one helper."""
import re
from pathlib import Path

from _commit_fixture import git, save
from _engine import REPO, cli
from _mw020 import built, deliverable, green, head, head_tree, index_digest, make_root, rows
from test_mw021_command import _task

RULES_LINE = re.compile(r"^(K\d\d)\s+\S+\s+\S+\s+(exists|missing)\s+last green tree (\S+)$")


def _last_green(out, ident):
    for line in out.splitlines():
        m = RULES_LINE.match(line.strip())
        if m and m.group(1) == ident:
            return m.group(3)
    raise AssertionError(f"no rules line for {ident}: {out}")


def test_rules_finds_a_green_row_written_as_the_commit_gate_writes_it(tmp_path):
    """E1: a row whose `tree` is the sha256 of `git ls-files -s -z` of a commit that holds the test file is the last
    green tree of that card: `mkway rules` shows the git tree id of that commit. Catches: a reader that takes the
    key for a git tree id and so prints `none` for a green row that exists."""
    root = _task(tmp_path)
    save(root, "rules/K01.md")
    save(root, "tests/rules/K01/test_K01.py")
    green(root, tree=index_digest(root))
    code, out, err = cli(root, "rules")
    assert code == 0, err
    assert _last_green(out, "K01") == head_tree(root)[:8]


def test_rules_finds_the_green_row_of_an_older_commit(tmp_path):
    """E2: the row names an older commit by the digest and HEAD has moved on; the card is still shown with the tree
    of the commit the row names, and a card whose test no green commit holds is still `none`. Catches: a key read
    only for HEAD, or a digest compared with the wrong commit."""
    root = _task(tmp_path)
    save(root, "rules/K01.md")
    save(root, "tests/rules/K01/test_K01.py")
    old_tree, old_key = head_tree(root), index_digest(root)
    save(root, "rules/K02.md")
    save(root, "src/later.py")
    green(root, tree=old_key)
    code, out, err = cli(root, "rules")
    assert code == 0, err
    assert _last_green(out, "K01") == old_tree[:8]
    assert _last_green(out, "K02") == "none"


def test_built_still_passes_on_the_same_row(tmp_path):
    """E3: the same digest row lets `mkway built` pass for HEAD and the provenance row keeps the key it found; a
    digest of another commit still refuses `built-untested`. Catches: the move to one helper breaking MW-020."""
    root = make_root(tmp_path)
    rel = deliverable(root)
    old_key = index_digest(root)
    save(root, "src/b.py")
    green(root, tree=old_key)
    assert built(root, rel)[0] != 0
    green(root, tree=index_digest(root))
    code, out, err = built(root, rel)
    assert code == 0, err
    assert rows(root, "deliverables.jsonl")[-1]["head"] == head(root)


def test_the_rules_view_shows_eight_hex_characters_whichever_form_the_row_used(tmp_path):
    """E4: a git tree id row and a digest row both show the 8 hex characters of the git tree id. Catches: a view
    that shows the digest for one form and the tree id for the other, or one longer than 8."""
    for form in ("id", "digest"):
        root = _task(tmp_path / form)
        save(root, "rules/K01.md")
        save(root, "tests/rules/K01/test_K01.py")
        green(root, tree=head_tree(root) if form == "id" else index_digest(root))
        shown = _last_green(cli(root, "rules")[1], "K01")
        assert re.fullmatch(r"[0-9a-f]{8}", shown), (form, shown)
        assert shown == head_tree(root)[:8], form


def test_one_helper_serves_the_writer_and_every_reader():
    """E5: the module of the commit gate's own tree computation holds the one function that names the tree keys of a
    commit; `deliverables.py` and `rules.py` call it and keep no second copy of the listing or the hash. Catches: a
    second definition of the key that drifts from the writer's."""
    import deliverables
    import gate_commit_tests
    import rules
    assert callable(gate_commit_tests.tree_keys)
    root = Path(REPO)
    keys = gate_commit_tests.tree_keys(root, "HEAD")
    assert keys[0] == git(root, "rev-parse", "HEAD^{tree}").strip() and len(keys) == 2
    for module in (deliverables, rules):
        text = Path(module.__file__).read_text(encoding="utf-8")
        assert "tree_keys" in text and "hashlib" not in text and '"ls-files"' not in text, module.__name__
    assert "tree_keys" in Path(gate_commit_tests.__file__).read_text(encoding="utf-8")


def test_the_register_changelog_and_card_name_the_card():
    """E6: `cards/REGISTER.md` has the MW-023 row, `## 0.2.0` of the changelog lists it, the card folder exists, and
    `VERSION` stays `0.2.0`. Catches: a fix that leaves the register and the changelog behind."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert re.search(r"^\| MW-023 \|.*`cards/MW-023-[a-z0-9-]+`", register, re.M)
    section = (REPO / "CHANGELOG.md").read_text(encoding="utf-8").split("## 0.2.0", 1)[1].split("## 0.1.0", 1)[0]
    assert "MW-023" in section
    assert list((REPO / "cards").glob("MW-023-*/CARD.md"))
    assert (REPO / "VERSION").read_text(encoding="utf-8").strip() == "0.2.0"

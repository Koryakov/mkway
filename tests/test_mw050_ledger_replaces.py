"""Card MW-050: `mkway ledger add --replaces <id>` links a new row to an earlier one; the earlier row then reads as
superseded while its line stays byte for byte as it was. Synthetic roots only."""
import json

from _engine import cli, task_root
import ledger

ADD = ("ledger", "add", "--card", "C-1", "--topic", "naming", "--quote", "use the short form", "--source", "chat")


def _profile(root):
    return json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))


def _file(root):
    return root / "mkway" / "ledger" / "ledger.md"


def test_replaces_an_existing_id_links_the_row_and_supersedes_the_old_one(tmp_path):
    """Checks: a link to an existing row is kept, the old row reads superseded, and the earlier lines stay byte for byte. E1."""
    root = task_root(tmp_path)
    assert cli(root, *ADD, session=True)[0] == 0
    assert cli(root, *ADD, session=True)[0] == 0
    before = _file(root).read_bytes()
    code, out, err = cli(root, *ADD, "--replaces", "D-1", session=True)
    assert code == 0, err
    after = _file(root).read_bytes()
    assert after.startswith(before)
    rows = {r["id"]: r for r in ledger.read(root, _profile(root))}
    assert rows["D-3"]["replaces"] == "D-1"
    assert rows["D-3"]["status"] == "in force"
    assert rows["D-1"]["status"] == "superseded"
    assert ledger.is_closed(rows["D-1"]["status"])
    assert rows["D-2"]["status"] == "in force"
    assert ledger.counts(root, _profile(root)) == (3, 2)


def test_replaces_an_unknown_id_is_refused_and_nothing_is_written(tmp_path):
    """Catches: a link to a row that does not exist, accepted or written to the ledger. E2."""
    root = task_root(tmp_path)
    code, _out, err = cli(root, *ADD, "--replaces", "D-9", session=True)
    assert code == 1
    assert "ledger-replaces-unknown" in err
    assert not _file(root).exists()
    assert cli(root, *ADD, session=True)[0] == 0
    before = _file(root).read_bytes()
    code, _out, err = cli(root, *ADD, "--replaces", "D-9", session=True)
    assert code == 1
    assert "ledger-replaces-unknown" in err
    assert _file(root).read_bytes() == before

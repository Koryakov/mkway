"""Card MW-112 part (v) (ruling R284), layer shell: the start block measures the role files the engine ships and prints
«role file: <path>, N/<budget> lines»; it never stops on the number. Synthetic task root under tmp_path."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: the shared helpers and `_engine`
from _engine import task_root  # noqa: E402
import dispatch  # noqa: E402
import startline  # noqa: E402


def _block(root):
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    return startline.render(root, root / "mkway" / "profile.json", profile, [], dispatch.load_manifest(dispatch.ENGINE_DIR),
                            {"CLAUDECODE": "1"}, session="s1")


def test_the_start_block_prints_one_line_per_role_file_with_its_count_and_budget(tmp_path):
    """Catches: a start block that does not measure the role files, so a file can outgrow its budget unseen."""
    lines = [x for x in _block(task_root(tmp_path)).splitlines() if x.startswith("role file: ")]
    counts = {n: sum(1 for x in (dispatch.ENGINE_DIR / "roles" / f"{n}.md").read_text(encoding="utf-8").splitlines() if x.strip())
              for n in ("lead", "builder", "operator")}
    assert [x.rsplit(", ", 1)[1] for x in lines] == [f"{counts['lead']}/40 lines", f"{counts['builder']}/30 lines",
                                                      f"{counts['operator']}/30 lines"]
    assert [x.split(", ")[0].rsplit("/", 1)[1] for x in lines] == ["lead.md", "builder.md", "operator.md"]


def test_a_role_file_over_its_budget_is_shown_and_never_stops_the_block(tmp_path, monkeypatch):
    """Catches: a start block that refuses or raises when a role file is over its budget; it only shows the number."""
    monkeypatch.setattr(startline, "ROLE_BUDGET", (("lead", 1), ("builder", 30), ("operator", 30)))
    block = _block(task_root(tmp_path))
    (line,) = [x for x in block.splitlines() if x.startswith("role file: ") and x.split(", ")[0].endswith("lead.md")]
    assert line.rsplit(", ", 1)[1].endswith("/1 lines")

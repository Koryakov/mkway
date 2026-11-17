"""The start line's gates for the delete entry (card MW-009, part P6). The README section checks (E31, E32) were
document checks and moved out (card MW-064, case_map.md)."""
from _engine import task_root
import dispatch
from _mw097_start_block import _block, _line, _names, _set_gates


def test_the_start_line_names_the_delete_gate_on_and_off(tmp_path):
    """Checks: with the real manifest the delete entry is on gates on, and off with its switch off, nothing else changes (E33, part 6)."""
    manifest = dispatch.load_manifest(dispatch.ENGINE_DIR)
    loaded = [e["name"] for e in manifest if e.get("function") and e.get("reason_ids")]
    assert "delete" in loaded
    root = task_root(tmp_path)
    block = _block(root, manifest)
    assert "delete" in _names(_line(block, "gates on:"))
    assert _line(block, "gates off:") == "gates off: none"
    profile = _set_gates(root, {"delete": {"on": False}})
    block = _block(root, manifest, profile)
    assert _names(_line(block, "gates off:")) == ["delete"]
    assert "delete" not in _names(_line(block, "gates on:"))

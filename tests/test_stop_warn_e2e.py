"""Card MW-075, layer e2e: the real hook command (`mkway.py hook Stop --group stop`) as a subprocess, with a Stop payload
and a profile without `outbox.checkers`. Synthetic task root; the replay is the real dedup case of 2026-11-12, a lead
stopping six times in a row."""
import json
import subprocess
import sys

from _engine import REPO, task_root
import leads
import profiles

LINE = "[mkway outbox_check.stop verdict-not-enforced] blind verdict not enforced: outbox.checkers missing in profile"


def _lead_root(tmp_path):
    root = task_root(tmp_path)
    profile = json.loads((root / "mkway" / "profile.json").read_text(encoding="utf-8"))
    leads.register_lead(profiles.shared_state_dir(root, profile), "lead-1")
    return root


def _stop(root):
    payload = json.dumps({"session_id": "lead-1", "hook_event_name": "Stop", "stop_hook_active": False})
    return subprocess.run([sys.executable, "-I", "-X", "utf8", str(REPO / "mkway.py"), "hook", "Stop", "--group", "stop"],
                          input=payload, capture_output=True, text=True, timeout=60, cwd=str(root),
                          env={"CLAUDE_PROJECT_DIR": str(root), "PATH": ""})


def test_the_real_stop_hook_shows_the_warning_to_the_user_and_does_not_continue(tmp_path):
    """Checks: the real Stop command exits zero and shows the missing-key warning as a systemMessage only, with no continue decision."""
    proc = _stop(_lead_root(tmp_path))
    assert (proc.returncode, json.loads(proc.stdout)) == (0, {"systemMessage": LINE})


def test_six_stops_in_a_row_print_the_line_once(tmp_path):
    """Catches: the replay of the dedup lead, six empty turns after six Stops; only the first Stop may print."""
    root = _lead_root(tmp_path)
    outs = [_stop(root).stdout for _ in range(6)]
    assert (json.loads(outs[0]), outs[1:]) == ({"systemMessage": LINE}, [""] * 5)

"""Agent records, part 4 (card MW-004): the README section «Agent records»."""
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.engine_repo  # the README is not in an installed copy (`mkway check` leaves this test out)

README = Path(__file__).resolve().parents[1] / "README.md"
MAX_LINES = 16  # «one short section»


def _section():
    text = README.read_text(encoding="utf-8")
    heads = [m for m in re.finditer(r"^## (.*)$", text, re.M)]
    mine = [i for i, m in enumerate(heads) if m.group(1).strip() == "Agent records"]
    assert len(mine) == 1, "exactly one `## Agent records` section"
    start = heads[mine[0]].end()
    end = heads[mine[0] + 1].start() if mine[0] + 1 < len(heads) else len(text)
    return text[start:end]


def test_readme_has_a_short_agent_records_section():
    """E21: one `## Agent records` section of at most 16 lines; it names both events, the state file, the profile
    key with its default, the gate switch, the two result sources and «not established»; it says the hook never
    blocks. Catches: a missing or doubled section, a section that does not say where the rows go or how to tune the
    cap, a long essay."""
    body = _section()
    lines = [line for line in body.splitlines() if line.strip()]
    assert 3 <= len(lines) <= MAX_LINES, len(lines)
    for word in ("SubagentStart", "SubagentStop", "agents.jsonl", "agents.cap_minutes", "default 30",
                 "gates.agents.on", "last_assistant_message", "agent_transcript_path", "not established",
                 "never blocks"):
        assert word in body, word

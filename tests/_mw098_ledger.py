"""Helper of card MW-098: the scan of the engine's own files for a ledger.add call with no by= argument (MW-049, E5). The loop
is moved here out of the test body (S1); the logic is the same as it was in the test."""
import re
from pathlib import Path


def bare_ledger_writes(engine):
    bare = []
    for path in sorted(Path(engine).glob("*.py")):
        if path.name == "ledger.py":
            continue
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"ledger\.add\(", text):
            depth, i = 1, m.end()
            while depth and i < len(text):
                depth += {"(": 1, ")": -1}.get(text[i], 0)
                i += 1
            if "by=" not in text[m.end():i]:
                bare.append(f"{path.name}:{text.count(chr(10), 0, m.start()) + 1}")
    return bare

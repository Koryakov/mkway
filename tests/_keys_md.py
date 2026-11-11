"""Parse engine/KEYS.md tables (helper for the tests, not a test module)."""
from pathlib import Path

KEYS_MD = Path(__file__).resolve().parents[1] / "engine" / "KEYS.md"


def section_rows(heading: str):
    """Body rows of the first table under the `## <heading>` section, as lists of stripped cells."""
    rows, inside = [], False
    for line in KEYS_MD.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().startswith(heading)
            continue
        if inside and line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            rows.append(cells)
    return rows[1:]  # drop the header row


def unquote(cell: str) -> str:
    return cell.strip().strip("`")

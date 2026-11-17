"""Helper of the engine's repository checks (card MW-096): the file walk of the English-only check, kept out of the test body."""
import re

CYRILLIC = re.compile("[" + chr(0x0400) + "-" + chr(0x04FF) + "]")  # built from code points: no letter in this file


def cyrillic_hits(files, base):
    """The `path:line` of each line of the files that holds a Cyrillic letter, paths relative to `base`."""
    bad = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            if CYRILLIC.search(line):
                bad.append(f"{path.relative_to(base).as_posix()}:{n}")
    return bad

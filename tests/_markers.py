"""The layer markers of the test concept (card MW-052). Not a test module. `conftest.py` puts them on each collected test;
`pytest.ini` registers them. The default run excludes nothing (merge runs all); `-m "not e2e"` is the owner's to use."""
from pathlib import PurePosixPath

E2E_PREFIXES = ("test_e2e", "test_mw030", "test_mw038")


def marks_for(path: str) -> set:
    """The layer marks of a test file path (relative to the repository or absolute, either slash)."""
    p = PurePosixPath(str(path).replace("\\", "/"))
    marks = set()
    if p.name.startswith(E2E_PREFIXES):
        marks.add("e2e")
    if "shell" in p.parts[:-1] and "tests" in p.parts[:-1]:
        marks.add("shell")
    return marks

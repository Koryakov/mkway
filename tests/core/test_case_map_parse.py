"""Card MW-089, layer core: the one pure reader of a case_map.md. Synthetic text only; a line is one entry, in order, with its
number, its raw text, its kind (blank, comment, mapping, dropped, malformed) and the fields of that kind. An entry is the tuple
(number, raw, kind, old, new, why, kept_id, kept_why); a field that does not belong to the kind is None."""
import pytest

import _engine  # noqa: F401
from core_red import parse_case_map


@pytest.mark.parametrize("text, expected", [
    ("tests/a.py::t -> tests/b.py::u",
     [(1, "tests/a.py::t -> tests/b.py::u", "mapping", "tests/a.py::t", "tests/b.py::u", None, None, None)]),
    ("tests/a.py::t -> dropped: covered by a doc",
     [(1, "tests/a.py::t -> dropped: covered by a doc", "dropped", "tests/a.py::t", None, "covered by a doc", None, None)]),
    ("# a note",
     [(1, "# a note", "comment", None, None, None, None, None)]),
    ("> a header",
     [(1, "> a header", "comment", None, None, None, None, None)]),
    ("   ",
     [(1, "   ", "blank", None, None, None, None, None)]),
    ("a -> b",
     [(1, "a -> b", "malformed", None, None, None, None, None)]),
    ("a.py::t -> core/b.py::u",
     [(1, "a.py::t -> core/b.py::u", "mapping", "a.py::t", "core/b.py::u", None, None, None)]),
    ("  tests/a.py::t -> tests/b.py::u  \r\n",
     [(1, "  tests/a.py::t -> tests/b.py::u  ", "mapping", "tests/a.py::t", "tests/b.py::u", None, None, None)]),
], ids=["mapping", "dropped", "hash_comment", "gt_comment", "blank", "malformed", "sides_as_written", "crlf_raw_kept"])
def test_a_line_is_classified_with_its_fields(text, expected):
    """Checks: each kind of line gets its kind and fields, the sides stay as written and the raw text is unstripped."""
    assert parse_case_map(text) == expected


def test_a_split_is_one_entry_per_line_with_the_same_left_side():
    """Checks: two lines that share a left side stay two entries, none is lost to the other."""
    text = "x.py::t -> y.py::u\nx.py::t -> z.py::v\n"
    assert parse_case_map(text) == [
        (1, "x.py::t -> y.py::u", "mapping", "x.py::t", "y.py::u", None, None, None),
        (2, "x.py::t -> z.py::v", "mapping", "x.py::t", "z.py::v", None, None, None)]


@pytest.mark.parametrize("text, expected", [
    ("# kept: tests/a.py::t - stays here",
     [(1, "# kept: tests/a.py::t - stays here", "comment", None, None, None, "tests/a.py::t", "stays here")]),
    ("# kept: tests/a.py::t (stays here)",
     [(1, "# kept: tests/a.py::t (stays here)", "comment", None, None, None, "tests/a.py::t", "stays here")]),
    ("# kept: nothing readable",
     [(1, "# kept: nothing readable", "comment", None, None, None, None, None)]),
], ids=["dash_form", "paren_form", "neither_form"])
def test_a_kept_comment_carries_its_id_and_why_in_either_form(text, expected):
    """Checks: both kept forms in use give the kept id and why, a kept line in neither form has them as None."""
    assert parse_case_map(text) == expected


def test_line_numbers_count_from_one_over_every_line_kind():
    """Checks: the number of an entry is its 1-based line in the text, blank and comment lines included."""
    text = "> head\n\nq.py::a -> r.py::b\nbroken\n"
    assert parse_case_map(text) == [
        (1, "> head", "comment", None, None, None, None, None),
        (2, "", "blank", None, None, None, None, None),
        (3, "q.py::a -> r.py::b", "mapping", "q.py::a", "r.py::b", None, None, None),
        (4, "broken", "malformed", None, None, None, None, None)]

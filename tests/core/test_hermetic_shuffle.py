"""Card MW-074 (decision: R177), rows E11 to E15: the pure shuffle of the tests of one folder and the choice of the seed.
Items are plain stand-ins with a `path`; no pytest session, no disk."""
from pathlib import PurePosixPath
from types import SimpleNamespace

from _hermetic import seed_for, shuffle_under

CORE = PurePosixPath("tests/core")


def _items(*paths):
    return [SimpleNamespace(path=PurePosixPath(p)) for p in paths]


def _names(items):
    return [i.path.name for i in items]


TEN = [f"tests/core/t{n}.py" for n in range(10)]


def test_the_same_seed_gives_the_same_order():
    """Checks: one seed on the same tests gives the same order twice."""
    first = _names(shuffle_under(_items(*TEN), CORE, 5))
    second = _names(shuffle_under(_items(*TEN), CORE, 5))
    assert len({tuple(first), tuple(second)}) == 1


def test_two_seeds_give_two_orders():
    """Catches: a shuffle that ignores its seed."""
    assert _names(shuffle_under(_items(*TEN), CORE, 1)) != _names(shuffle_under(_items(*TEN), CORE, 2))


def test_a_shuffle_keeps_every_test_exactly_once():
    """Catches: a shuffle that drops or doubles a test."""
    names = _names(shuffle_under(_items(*TEN), CORE, 3))
    ordered = sorted(names)
    assert ordered == ["t0.py", "t1.py", "t2.py", "t3.py", "t4.py", "t5.py", "t6.py", "t7.py", "t8.py", "t9.py"]


def test_tests_outside_the_folder_keep_their_places():
    """Catches: a shuffle that moves a test which is not in the hermetic folder."""
    out = shuffle_under(_items("x/a.py", "tests/core/b.py", "tests/core/c.py", "tests/core/d.py", "y/e.py"), CORE, 3)
    assert [_names(out)[0], _names(out)[4]] == ["a.py", "e.py"]


def test_the_seed_is_the_given_one_or_the_clock():
    """Checks: a given seed wins; with none the seed is the whole seconds of the clock."""
    assert (seed_for(7, 1700000000.9), seed_for(None, 1700000000.9)) == (7, 1700000000)

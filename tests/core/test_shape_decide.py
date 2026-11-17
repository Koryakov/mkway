"""Card MW-073 (decision: R177), layer core: the shape decision of a commit's tests, a pure table. Synthetic sources only:
every source below is text handed to the decision, never a test that runs. One refusal row per rule S1 to S7 with its
nearest allow, then the diff rules (only functions added or changed are judged), then the text."""
import pytest

import _engine  # noqa: F401
from core_shape import Facts, Source, decide, refusal_text

PATH = "tests/test_x.py"
CORE_PATH = "tests/core/test_x.py"
DOC = '    """Checks: one thing."""\n'


def _test(body, *, doc=DOC, args="", decorator=""):
    """The source of one test function named `test_a`."""
    return f"{decorator}def test_a({args}):\n{doc}{body}"


def _param(name):
    """The decorator line of a parametrized test source."""
    values = (2,)
    at = chr(64)
    return f"{at}pytest.mark.parametrize({name!r}, {values})\n"


def _breaks(new, old=None, path=PATH):
    """[(function, rule)] the decision names for one source."""
    verdict = decide(Facts((Source(path, new, old),)))
    return [(b.function, b.rule) for b in verdict.breaches]


@pytest.mark.parametrize("body", [
    "    for x in (1, 2):\n        assert x\n",
    "    while False:\n        assert 1 == 1\n",
    "    if 1 == 1:\n        assert 2 == 2\n",
], ids=["for", "while", "if"])
def test_a_test_with_a_loop_or_a_branch_is_refused_as_s1(body):
    """Catches: a test that loops or branches, so one name hides many cases and a failure does not say which."""
    assert _breaks(_test(body)) == [("test_a", "S1")]


def test_a_parametrized_test_with_no_loop_is_allowed():
    """Checks: the way to many cases is pytest.mark.parametrize, which has no loop in the body."""
    source = _test("    assert x == 2\n", args="x", decorator=_param("x"))
    assert _breaks(source) == []


def test_a_test_with_no_assert_is_refused_as_s2():
    """Catches: a test that runs code and checks nothing, so it passes whatever the code does."""
    assert _breaks(_test("    x = 1 + 1\n")) == [("test_a", "S2")]


def test_a_test_with_only_pytest_raises_is_allowed():
    """Checks: a `with pytest.raises` is a check, so a test made of it needs no assert."""
    assert _breaks(_test("    with pytest.raises(ValueError):\n        int('x')\n")) == []


@pytest.mark.parametrize("body", [
    "    assert True\n",
    "    assert False\n",
    "    assert 1 == 1 and 2 == 2\n",
], ids=["true", "false", "and"])
def test_a_constant_or_composite_assert_is_refused_as_s3(body):
    """Catches: an assert that cannot fail, always fails, or hides two checks in one line."""
    assert _breaks(_test(body)) == [("test_a", "S3")]


def test_an_assert_of_one_comparison_is_allowed():
    """Checks: one comparison with a message, and a negated one, are plain asserts."""
    assert _breaks(_test("    assert 1 + 1 == 2, 'sum'\n    assert not 1 == 2\n")) == []


@pytest.mark.parametrize("doc", [
    "",
    '    """Does a thing."""\n',
    '    """Catches: a thing\n    on two lines."""\n',
], ids=["none", "no-word", "two-lines"])
def test_a_test_without_a_one_line_catches_or_checks_docstring_is_refused_as_s4(doc):
    """Catches: a test whose docstring does not say in one line what it catches or checks."""
    assert _breaks(_test("    assert 1 == 1\n", doc=doc)) == [("test_a", "S4")]


@pytest.mark.parametrize("doc", ['    """Catches: a failure."""\n', '    """Checks: an allow."""\n'],
                         ids=["catches", "checks"])
def test_a_catches_line_and_a_checks_line_are_allowed(doc):
    """Checks: both words of the rule open an accepted one-line docstring."""
    assert _breaks(_test("    assert 1 == 1\n", doc=doc)) == []


def test_a_one_line_pins_docstring_is_allowed():
    """Checks: a one-line Pins: docstring opens an accepted docstring, as Catches: and Checks: do."""
    assert _breaks(_test("    assert 1 == 1\n", doc='    """Pins: the present behaviour."""\n')) == []


@pytest.mark.parametrize("body", [
    "    import test_other\n    assert test_other\n",
    "    from test_other import x\n    assert x\n",
    "    from tests.helpers import x\n    assert x\n",
    "    text = read('tests/test_other.py')\n    assert text\n",
], ids=["import", "from-import", "tests-package", "literal-path"])
def test_a_test_that_imports_or_names_another_test_module_is_refused_as_s5(body):
    """Catches: a test coupled to another test file, which then cannot move or change alone."""
    assert _breaks(_test(body)) == [("test_a", "S5")]


@pytest.mark.parametrize("body", [
    "    import _helper\n    assert _helper\n",
    "    from _engine import task_root\n    assert task_root\n",
], ids=["import", "from-import"])
def test_an_import_of_an_underscore_helper_is_allowed(body):
    """Checks: a helper module that starts with an underscore is not a test module."""
    assert _breaks(_test(body)) == []


def test_a_module_level_import_of_a_test_module_in_a_new_file_is_refused_as_s5():
    """Catches: a new test file that imports another test module at its top, outside any function."""
    source = "import test_other\n\n\n" + _test("    assert 1 == 1\n")
    assert _breaks(source) == [("<module>", "S5")]


@pytest.mark.parametrize("body", [
    "    time.sleep(1)\n    assert 1 == 1\n",
    "    socket.socket()\n    assert 1 == 1\n",
    "    requests.get('x')\n    assert 1 == 1\n",
    "    urllib.request.urlopen('x')\n    assert 1 == 1\n",
    "    http.client.HTTPConnection('x')\n    assert 1 == 1\n",
    "    assert read('/var/data/x') == 1\n",
    "    assert read('C:\\\\data\\\\x') == 1\n",
], ids=["sleep", "socket", "requests", "urllib", "http", "posix-path", "windows-path"])
def test_a_test_that_sleeps_uses_the_network_or_an_absolute_path_is_refused_as_s6(body):
    """Catches: a slow or networked test, or one tied to a folder that exists on one machine only."""
    assert _breaks(_test(body)) == [("test_a", "S6")]


def test_a_test_that_builds_its_paths_from_tmp_path_is_allowed():
    """Checks: paths made from tmp_path, relative literals and an f-string tail are not absolute path literals."""
    body = ("    target = tmp_path / 'a' / 'b.txt'\n    other = f'{tmp_path}/c.txt'\n"
            "    joined = str(tmp_path) + '/d.txt'\n    assert target.name == 'b.txt'\n")
    assert _breaks(_test(body, args="tmp_path")) == []


@pytest.mark.parametrize("body", [
    "    assert decide(1) == decide(1)\n",
    "    assert decide(1) == compute_expected(1)\n",
    "    want = decide(2)\n    assert decide(1) == want\n",
], ids=["same-call", "helper-call", "name-from-call"])
def test_a_core_test_that_compares_with_a_call_is_refused_as_s7(body):
    """Catches: an expected value computed by the code under test, which agrees with it whatever it does."""
    assert _breaks(_test(body), path=CORE_PATH) == [("test_a", "S7")]


@pytest.mark.parametrize("body, args, decorator", [
    ("    assert decide(1) == (1, 'a')\n", "", ""),
    ("    assert decide(1) == frozenset({1})\n", "", ""),
    ("    assert decide(1) == want\n", "want", _param("want")),
    ("    assert 3 == decide(1)\n", "", ""),
], ids=["tuple", "frozenset", "parameter", "literal-on-the-left"])
def test_a_core_test_that_compares_with_a_literal_or_a_parameter_is_allowed(body, args, decorator):
    """Checks: an expected side that is a literal, a literal constructor or a parametrize argument is independent."""
    assert _breaks(_test(body, args=args, decorator=decorator), path=CORE_PATH) == []


def test_the_same_call_comparison_outside_tests_core_is_allowed():
    """Checks: S7 is the rule of tests under tests/core only."""
    assert _breaks(_test("    assert decide(1) == decide(1)\n")) == []


OLD_BAD = ("def test_old_loop():\n    for x in (1,):\n        assert x\n\n\n"
           "def test_old_empty():\n    pass\n")


def test_an_old_function_that_did_not_change_is_not_judged():
    """Checks: two old bad tests stay as they are while a good one is added; only the added one is judged."""
    new = "\n# a comment\n\n" + OLD_BAD + "\n\n" + _test("    assert 1 == 1\n")
    assert _breaks(new, OLD_BAD) == []


def test_a_changed_function_is_judged():
    """Catches: an old bad test that is edited and so escapes the judgement of the commit that edits it."""
    new = OLD_BAD.replace("for x in (1,)", "for x in (1, 2)")
    assert _breaks(new, OLD_BAD) == [("test_old_loop", "S1"), ("test_old_loop", "S4")]


def test_a_new_function_is_judged_and_the_old_one_is_not_named():
    """Catches: a new bad test hidden beside old tests of the same file."""
    old = _test("    assert 1 == 1\n")
    new = old + "\n\ndef test_b():\n    pass\n"
    assert _breaks(new, old) == [("test_b", "S2"), ("test_b", "S4")]


def test_a_helper_that_is_not_a_test_is_not_judged():
    """Checks: a function whose name does not start with test_ may loop and branch."""
    assert _breaks("def _build():\n    for x in (1,):\n        if x:\n            pass\n") == []


def test_a_method_of_a_test_class_is_judged_by_its_dotted_name():
    """Catches: a bad test hidden inside a Test class."""
    source = "class TestX:\n    def test_m(self):\n        pass\n\n    def helper(self):\n        pass\n"
    assert _breaks(source) == [("TestX.test_m", "S2"), ("TestX.test_m", "S4")]


def test_a_file_that_is_not_a_test_file_is_not_judged():
    """Checks: only files named test_*.py are judged."""
    assert _breaks(_test("    pass\n"), path="tests/helpers.py") == []


def test_the_refusal_names_the_file_the_function_and_the_rule():
    """Catches: a refusal that does not say which function of which file breaks which rule."""
    text = refusal_text(decide(Facts((Source(PATH, _test("    for x in (1,):\n        assert x\n")),))))
    assert "tests/test_x.py::test_a: S1" in text
    assert "pytest.mark.parametrize" in text


def test_the_text_shows_ten_breaches_and_counts_the_rest():
    """Catches: a refusal that prints every breach of a big file, or hides how many there are."""
    many = "".join(f"def test_n{n}():\n    '''Checks: x.'''\n    assert 1 == 1 and 2 == 2\n\n\n" for n in range(12))
    text = refusal_text(decide(Facts((Source(PATH, many),))))
    assert "12 breaches" in text
    assert "test_n9: S3" in text
    assert "test_n10" not in text
    assert "2 more" in text


def test_a_source_that_does_not_parse_is_listed_and_not_refused():
    """Checks: a file that is not Python is the test run's to report; the decision lists it and allows."""
    verdict = decide(Facts((Source(PATH, "def test_a(:\n"),)))
    assert (verdict.allowed, verdict.unparsed) == (True, (PATH,))

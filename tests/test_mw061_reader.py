"""Card MW-061: a newline inside single or double quotes (and inside a here-doc body) is part of the word, as bash reads
it; a newline outside quotes still separates commands. One reader (`helpers.parse`) serves every gate, so these tables
read it directly. The refusal log keeps the whole command, newlines shown as `\\n`. Synthetic text only."""
import pytest

from _engine import REPO  # noqa: F401  (puts the engine folder on the path)
import helpers
import logs

REAL = ('git commit -m "#90001 ZZ-001 Add the totals report plan\n\n'
        '  Trailer: second paragraph <angle text>" -- report tests/report_plan')

# (id, command, message, paths)
ONE_COMMIT = [
    ("double quotes", 'git commit -m "first\nsecond" -- a b', "first\nsecond", ["a", "b"]),
    ("double quotes, empty line", 'git commit -m "first\n\nsecond" -- a b', "first\n\nsecond", ["a", "b"]),
    ("single quotes", "git commit -m 'first\nsecond' -- a b", "first\nsecond", ["a", "b"]),
    ("single quotes, empty line", "git commit -m 'first\n\n  second' -- a b", "first\n\n  second", ["a", "b"]),
    ("two -m", 'git commit -m "first\nline" -m "second\nline" -- a b', "first\nline\n\nsecond\nline", ["a", "b"]),
    ("the real shape", REAL,
     "#90001 ZZ-001 Add the totals report plan\n\n  Trailer: second paragraph <angle text>",
     ["report", "tests/report_plan"]),
    ("a heredoc marker inside quotes is text", 'git commit -m "see <<EOF\nnot a heredoc" -- a b',
     "see <<EOF\nnot a heredoc", ["a", "b"]),
    ("a heredoc word after the quotes", "git commit -m 'one\ntwo' -- a b <<EOF\nbody\nEOF", "one\ntwo", ["a", "b"]),
    ("a comment mark inside quotes is text", 'git commit -m "one\n# two" -- a b', "one\n# two", ["a", "b"]),
    ("a quote of the other kind inside", 'git commit -m "it\'s\nhere" -- a b', "it's\nhere", ["a", "b"]),
    ("a carriage return and a line feed", 'git commit -m "one\r\ntwo" -- a b', "one\r\ntwo", ["a", "b"]),
]


@pytest.mark.parametrize("name, command, message, paths", ONE_COMMIT, ids=[c[0] for c in ONE_COMMIT])
def test_a_newline_inside_quotes_is_part_of_the_word(name, command, message, paths):
    """Catches: a command cut at the first newline inside quotes, so the gate takes the whole index. E1."""
    (found,) = helpers.commit_cmd(command)
    assert found.message == message
    assert found.paths == paths
    assert [s.words for s in helpers.parse(command)][0][:3] == ["git", "commit", "-m"]


def test_a_heredoc_body_is_part_of_the_message():
    """Checks: a message from a here-doc keeps its empty line, and the paths named on the command line are seen. E1."""
    command = "git commit -F - -- a b <<'EOF'\nfirst\n\nsecond\nEOF"
    (found,) = helpers.commit_cmd(command)
    assert found.message == "first\n\nsecond"
    assert found.paths == ["a", "b"]
    command = "git commit -m \"$(cat <<'EOF'\nfirst\n\nsecond\nEOF\n)\" -- a b"
    assert [c.paths for c in helpers.commit_cmd(command)] == [["a", "b"]]


def test_a_newline_outside_quotes_still_separates_commands():
    """Checks: two lines are two commands, and a quoted newline in the second does not merge or split them. E2."""
    command = 'git add a\ngit commit -m "one\ntwo" -- b'
    simples = helpers.parse(command)
    assert [s.words[:2] for s in simples] == [["git", "add"], ["git", "commit"]]
    (found,) = helpers.commit_cmd(command)
    assert found.message == "one\ntwo"
    assert found.paths == ["b"]
    assert [s.words[0] for s in helpers.parse("echo a\n\necho b")] == ["echo", "echo"]


def test_the_rules_of_quoted_text_stay_as_they_were():
    """Checks: substitutions and variable expansion inside quoted text still work when the text holds a newline. E4 (MW-048)."""
    assert helpers.parse('echo "a\n$(whoami)\nb"')[0].subs == ["whoami"]
    assert helpers.parse('echo "a\n`whoami`"')[0].subs == ["whoami"]
    assert helpers.parse('echo "a\n$(whoami)\nb"')[0].words == ["echo", "a\n$(whoami)\nb"]
    assert helpers.parse("echo 'a\nb $x'")[0].words == ["echo", "a\nb $x"]


def test_the_refusal_log_keeps_the_whole_command_with_newlines_shown_as_backslash_n():
    """Checks: the refusal target is the whole command with each newline shown as backslash n, cut at the usual length. E5."""
    target = logs.target_of({"command": REAL})
    assert target.startswith("git commit -m \"#90001 ZZ-001 Add the totals report plan\\n\\n  Trailer")
    assert "\n" not in target
    assert "\r" not in target
    assert logs.target_of({"command": "echo " + "x" * 300}) == "echo " + "x" * 195
    short = 'git commit -m "a\nb" -- c d'
    assert logs.target_of({"command": short}) == 'git commit -m "a\\nb" -- c d'


def test_the_text_after_a_heredoc_body_is_the_next_command():
    """Checks: the body of a here-doc, even with a lone quote, and its delimiter line are taken out. E2."""
    command = "cat <<EOF\nbody 'with a quote\nEOF\ngit commit -m x -- a"
    simples = helpers.parse(command)
    assert [s.words[0] for s in simples] == ["cat", "git"]
    assert simples[0].heredocs == ["body 'with a quote"]
    assert [c.paths for c in helpers.commit_cmd(command)] == [["a"]]


def test_two_heredocs_on_one_line_take_their_bodies_in_order():
    """Checks: two here-docs on one line take their bodies in order, the first marker first. E2."""
    (simple,) = helpers.parse("cat <<A <<B\n1\nA\n2\nB")
    assert simple.heredocs == ["1", "2"]


def test_a_comment_hides_a_marker():
    """Catches: a marker inside a comment read as a here-doc, so the next line is swallowed. E2."""
    command = "echo a # see <<EOF\ngit commit -m x -- p"
    assert [c.paths for c in helpers.commit_cmd(command)] == [["p"]]


def test_a_heredoc_with_no_delimiter_line_does_not_crash_the_reader():
    """Catches: a here-doc with no delimiter line crashing the reader. E2."""
    (simple,) = helpers.parse("cat <<EOF\nbody\nmore")
    assert simple.words == ["cat"]
    assert simple.heredocs == ["body\nmore"]


@pytest.mark.parametrize("shell", ["bash", "powershell"])
def test_a_marker_inside_double_quotes_is_text_in_both_shells(shell):
    """Checks: a marker inside double quotes is text for both the Bash and the PowerShell tool. E2."""
    (simple,) = helpers.parse('echo "a <<EOF\nb"', shell)
    assert simple.words == ["echo", "a <<EOF\nb"]

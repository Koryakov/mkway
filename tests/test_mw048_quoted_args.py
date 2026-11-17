"""MW-048: the plain-call check reads the structure outside quotes only; the content of a quoted argument is literal
text, except what the shell still expands inside double quotes (`$name`, `$(...)`, a backtick). `--quote-file` accepts
a file under the bundle's asks folder or ledger folder. Synthetic roots only."""
import pytest

from test_lock import gtask, shell  # noqa: F401  (gtask is a fixture)

P = "python mkway/engine/mkway.py"
LEDGER = f"{P} ledger add --card C-1 --topic t --source s"
QUOTE = "Definitely no. We shouldn't. (10536)."


def _kind(v):
    return v.reason_id if v.kind == "refuse" else "allow"


@pytest.mark.parametrize("tool,command", [
    ("Bash", f'{LEDGER} --quote "{QUOTE}"'),
    ("PowerShell", f'{LEDGER} --quote "{QUOTE}"'),
    ("Bash", f'{LEDGER} --quote "a; b | c > d"'),
    ("PowerShell", f'{LEDGER} --quote "a; b | c > d"'),
    ("Bash", f"{LEDGER} --quote 'a; b | $(x) `y` $z (1)'"),
    ("PowerShell", f"{LEDGER} --quote 'a; b | $(x) $z (1)'"),
    ("Bash", f'{LEDGER} --topic "t {{x}} [y] *?"'),
])
def test_quoted_content_is_literal_and_allowed(gtask, tool, command):
    """Checks: the content of a quoted argument is literal text, and the plain call is allowed."""
    assert _kind(shell(gtask, command, tool=tool)) == "allow", command


@pytest.mark.parametrize("tool,command", [
    ("Bash", f'{LEDGER} --quote "x" ; rm y'),
    ("Bash", f'{LEDGER} --quote "x" | cat'),
    ("Bash", f'{LEDGER} --quote "x" > out.txt'),
    ("PowerShell", f'{LEDGER} --quote "x" ; rm y'),
])
def test_a_real_chain_outside_quotes_is_refused(gtask, tool, command):
    """Catches: a real chain or redirect outside the quotes that passes as a plain call."""
    assert _kind(shell(gtask, command, tool=tool)) == "engine-call-not-plain", command


@pytest.mark.parametrize("tool,command", [
    ("Bash", f'{LEDGER} --quote "$(whoami)"'),
    ("Bash", f'{LEDGER} --quote "a `whoami` b"'),
    ("Bash", f'{LEDGER} --quote "cost $HOME"'),
    ("PowerShell", f'{LEDGER} --quote "$(whoami)"'),
    ("PowerShell", f'{LEDGER} --quote "cost $env:HOME"'),
])
def test_expansion_inside_double_quotes_stays_refused(gtask, tool, command):
    """Catches: an expansion inside double quotes that passes as literal text."""
    assert _kind(shell(gtask, command, tool=tool)) == "engine-call-not-plain", command


def test_the_refusal_names_the_fix(gtask):
    """Catches: a refusal that does not name the asks folder, the quote-file option or the dollar sign or backtick fix."""
    v = shell(gtask, f'{LEDGER} --quote "$(whoami)"')
    assert v.kind == "refuse"
    text = v.message if hasattr(v, "message") else str(v)
    assert "mkway/asks" in text, text
    assert "--quote-file" in text, text
    assert "dollar sign or backtick" in text, text


@pytest.mark.parametrize("path", ["mkway/asks/q.txt", "mkway/ledger/quote.txt"])
def test_quote_file_inside_asks_or_ledger_is_accepted(gtask, path):
    """Checks: a quote file under the asks folder or the ledger folder is accepted."""
    assert _kind(shell(gtask, f"{LEDGER} --quote-file {path}")) == "allow"


@pytest.mark.parametrize("path", ["src/q.txt", "mkway/state/q.txt", "../q.txt"])
def test_quote_file_outside_asks_and_ledger_is_refused(gtask, path):
    """Catches: a quote file outside the asks and ledger folders that is accepted."""
    assert _kind(shell(gtask, f"{LEDGER} --quote-file {path}")) == "quote-file-outside"

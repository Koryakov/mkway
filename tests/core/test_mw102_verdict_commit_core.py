"""Card MW-102 (decision: R254), layer core: the commit gate's pure decision for the verdict file `tests/verdicts/<card>.md`.
The orderer of card X (and only the orderer) may commit that file; the holder never may; a commit that takes it is refused
`verdict-unproven` when the shell's proof facts say a row has no record. The shell hands the verdict path of each ordered card
(`core.Ordered.verdict`), the verdict folder (`Facts.verdict_dir`) and the proof facts (`CommitFacts.unproven`) over; the core
reads nothing. Synthetic ids only."""
import _engine  # noqa: F401  (puts the engine folder on the import path)
import core
import helpers
import pytest
from _no_io import no_io

BUILTINS = frozenset(helpers.git_builtins())  # read here, before any guard: the shell hands it over as a fact
CARD_RE = r"(?<![A-Za-z0-9_-])CARD-[0-9]{3,}(?![0-9A-Za-z_])"
EXEMPT = ("mkway/cards/REGISTER.md", "mkway/ledger")
FOLDER_1, FOLDER_2 = "mkway/cards/CARD-001-first", "mkway/cards/CARD-002-second"
V1, V2 = "tests/verdicts/CARD-001.md", "tests/verdicts/CARD-002.md"


def _one():
    return core.Ordered("CARD-001", FOLDER_1, frozenset({"src"}), V1)


def _two():
    return core.Ordered("CARD-002", FOLDER_2, frozenset({"src/two"}), V2)


NODE = "tests/test_a.py::test_one"
SENTENCE = "an orderer may commit only the folders of cards it ordered plus REGISTER.md"


def _taken(*rels):
    return tuple(("M", rel, "index") for rel in rels)


def _commit(*rels, message="CARD-001 verdict", **kw):
    return core.CommitFacts(message=message, taken=_taken(*rels), sizes={rel: 1 for rel in rels}, ignored=frozenset(), **kw)


def _facts(commit, **kw):
    base = dict(command="git commit -m 'CARD-001 verdict'", git_builtins=BUILTINS, commits=(commit,), exempt=EXEMPT,
                card_id_pattern=CARD_RE, verdict_dir="tests/verdicts")
    base.update(kw)
    return core.Facts(**base)


def _orderer(commit, **kw):
    """A session that holds no card and ordered CARD-001 (held by `b1`) and CARD-002 (held by `b2`)."""
    base = dict(ordered=(_one(), _two()), holders={"CARD-001": "b1", "CARD-002": "b2"})
    base.update(kw)
    return _facts(commit, **base)


def _holder(commit, paths=frozenset({"tests/verdicts"}), **kw):
    """A session that holds the open card CARD-001 (folder `FOLDER_1`) and ordered nothing."""
    return _facts(commit, card_id="CARD-001", card_found=True, card_status="open", card_paths=paths, card_folder=FOLDER_1,
                  **kw)


def _verdict(facts):
    with no_io():
        found = core.decide_commit(facts)
    return found.reason if found.kind == core.REFUSE else None, found.text


def test_the_orderer_commits_the_verdict_file_of_a_card_it_ordered():
    """Checks: an orderer that holds no card stages `tests/verdicts/CARD-001.md` of the card it ordered and the verdict is allow."""
    assert _verdict(_orderer(_commit(V1)))[0] is None


def test_the_orderer_is_refused_the_verdict_file_of_a_card_it_did_not_order():
    """Catches: an orderer committing the verdict file of a card another session ordered."""
    reason, text = _verdict(_orderer(_commit(V2, message="CARD-002 verdict"), ordered=(_one(),)))
    assert (reason, "tests/verdicts/CARD-002.md" in text, "orderer of CARD-002" in text) == ("file-not-in-card", True, True)


def test_the_holder_never_commits_its_own_cards_verdict_file():
    """Catches: the holder of CARD-001 committing its own verdict file because its Paths cover `tests/verdicts`."""
    reason, text = _verdict(_holder(_commit(V1)))
    assert (reason, "the holder never commits its own card's verdict file" in text) == ("file-not-in-card", True)


def test_a_holder_whose_paths_cover_another_cards_verdict_file_is_refused():
    """Catches: a holder committing the verdict file of a card it holds none of, because its Paths cover the folder."""
    reason, text = _verdict(_holder(_commit(V2, message="CARD-001 verdict")))
    assert (reason, "tests/verdicts/CARD-002.md" in text, "orderer of CARD-002" in text) == ("file-not-in-card", True, True)


def test_the_holder_commits_a_plain_test_file_inside_its_paths():
    """Checks: the nearest allow of the holder rows: the same holder stages a file in a sub-folder of the verdict folder, which is no verdict file."""
    assert _verdict(_holder(_commit("tests/verdicts/notes/n.md")))[0] is None


def test_the_orderer_commits_the_verdict_file_with_card_md():
    """Checks: the verdict file and `CARD.md` of the same ordered card in one commit are allowed."""
    assert _verdict(_orderer(_commit(V1, f"{FOLDER_1}/CARD.md")))[0] is None


def test_an_orderer_that_also_holds_the_card_is_refused_its_verdict_file():
    """Catches: one session that ordered and holds a card committing its verdict file."""
    facts = _orderer(_commit(V1), card_id="CARD-001", card_found=True, card_status="open", card_paths=frozenset({"tests/verdicts"}),
                     card_folder=FOLDER_1)
    reason, text = _verdict(facts)
    assert (reason, "the holder never commits its own card's verdict file" in text) == ("file-not-in-card", True)


def test_the_orderer_sentence_names_the_verdict_file():
    """Catches: a refusal of an orderer that leaves the verdict file out of the sentence naming what an orderer may commit."""
    reason, text = _verdict(_orderer(_commit(V1, "src/a.py")))
    assert (reason, SENTENCE in text, "the verdict file of each card it ordered" in text, "src/a.py" in text, V1 in text) == (
        "file-not-in-card", True, True, True, False)


def test_an_unproven_row_is_refused_naming_the_node():
    """Catches: a verdict file committed with a row the proof says has no record, and a refusal that does not name the node."""
    proof = {V1: ((NODE, "no record of verdict add for this row"),)}
    reason, text = _verdict(_orderer(_commit(V1, unproven=proof)))
    assert (reason, NODE in text, "no record of verdict add for this row" in text) == ("verdict-unproven", True, True)


def test_rows_that_are_all_proved_are_allowed():
    """Checks: the nearest allow of the unproven row: the proof facts hold no unproven row for the verdict file."""
    assert _verdict(_orderer(_commit(V1, unproven={V1: ()})))[0] is None


def test_a_message_that_names_no_card_of_the_verdict_commit_is_refused():
    """Catches: a verdict commit whose message names no card it takes a file of."""
    reason, text = _verdict(_orderer(_commit(V1, message="the verdict")))
    assert (reason, "CARD-001" in text) == ("commit-message-card", True)


def test_a_message_that_names_the_card_of_the_verdict_commit_is_allowed():
    """Checks: the nearest allow of the message rule: the message names the card whose verdict file the commit takes."""
    assert _verdict(_orderer(_commit(V1, message="CARD-001 the verdict")))[0] is None

"""Card MW-107 (concept line 1, kind K6): the meta test of the owner table. A profile key that names a folder or a pattern of
files must have an owner row in `engine/owners.py` or a stated reason why it is no write target; a key added to the schema
later without either fails this suite, never a running task. Hermetic: the schema is read as text. Synthetic values only."""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ENGINE = REPO / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

# R274e (13): every string or array leaf of the schema is classified, by its type and never by the words of its description:
# an owner row or a stated reason (`owners.PROFILE_KEYS`, `owners.NOT_TARGETS`), or text, a name, an id, a command or a mode: no place
TEXT_KEYS = {
    "vcs", "lock_gate.git_builtins_extra", "product_checks", "ids.decision_row", "ids.rule_card", "ids.work_item", "ids.evidence",
    "ids.card_prefix", "outbox.checkers", "python.command", "user.protected_hooks", "cards.owner_moves", "cards.approver",
    "cards.verdicts", "register.columns", "test_env", "wake.mode", "notify.command", "owner_ask.markers", "owner_ask.sources",
    "commit.message_prefix", "tests.command", "tests.red_proof.mode", "tests.red_proof.decision_pattern", "tests.verdict_add.mode",
}


def schema_text_or_list_keys():
    """The dotted keys of the profile schema whose type is a string or an array: the keys that can hold a folder or a pattern."""
    schema = json.loads((ENGINE / "profile.schema.json").read_text(encoding="utf-8"))
    found = []

    def walk(node, prefix):
        for key, value in node.get("properties", {}).items():
            if value.get("type") == "object" and "properties" in value:
                walk(value, prefix + key + ".")
            elif value.get("type") in ("string", "array"):
                found.append(prefix + key)

    walk(schema, "")
    return sorted(set(found))


def test_every_string_or_array_key_of_the_schema_has_an_owner_row_a_reason_or_is_listed_as_text():
    """Catches: a profile key that can hold a folder or a pattern and has neither an owner row, nor a stated reason, nor a place in the list of text keys."""
    import owners
    known = set(owners.PROFILE_KEYS) | set(owners.NOT_TARGETS) | TEXT_KEYS
    assert sorted(set(schema_text_or_list_keys()) - known) == []


def test_no_key_of_the_owner_table_or_of_the_text_list_is_gone_from_the_schema():
    """Catches: an owner row, a reason or a text entry for a profile key the schema no longer has."""
    import owners
    known = set(owners.PROFILE_KEYS) | set(owners.NOT_TARGETS) | TEXT_KEYS
    assert sorted(known - set(schema_text_or_list_keys())) == []


def test_no_key_is_both_a_place_and_text():
    """Checks: the three classes do not overlap, so a key that names a folder is never hidden among the text keys."""
    import owners
    assert (set(owners.PROFILE_KEYS) & TEXT_KEYS, set(owners.NOT_TARGETS) & TEXT_KEYS, set(owners.PROFILE_KEYS) & set(owners.NOT_TARGETS)) == (
        set(), set(), set())


@pytest.mark.parametrize("key, value, sample, kind", [
    pytest.param("bundle.root", "zzb", "zzb/cards/C-1/CARD.md", "card-file", id="bundle-root"),
    pytest.param("owner_ask.dir", "zza", "zza/q_ask.md", "asks", id="owner-ask-dir"),
    pytest.param("outbox.dir", "zzo", "zzo/d.md", "outbox", id="outbox-dir"),
    pytest.param("outbox.id_patterns_file", "zzp/ids.txt", "zzp/ids.txt", "task-input", id="outbox-id-patterns-file"),
    pytest.param("paths.exempt", ["zze/**"], "zze/x.md", "exempt", id="paths-exempt"),
    pytest.param("test_roots", ["zzt"], "zzt/test_a.py", "work-files", id="test-roots"),
    pytest.param("knowledge.files", ["zzk/a.md"], "zzk/a.md", "work-files", id="knowledge-files"),
    pytest.param("questions.files", ["zzq/q.md"], "zzq/q.md", "work-files", id="questions-files"),
    pytest.param("deliverables.paths", ["zzd/*.xlsx"], "zzd/a.xlsx", "work-files", id="deliverables-paths"),
    pytest.param("deliverables.require_base", ["zzr/*.md"], "zzr/a.md", "work-files", id="deliverables-require-base"),
    pytest.param("rules.cards", ["zzc/*.md"], "zzc/a.md", "work-files", id="rules-cards"),
    pytest.param("rules.test_for", "zzu/{id}/t_{id}.py", "zzu/A/t_A.py", "work-files", id="rules-test-for"),
    pytest.param("tests.hermetic_dirs", ["zzh"], "zzh/test_a.py", "work-files", id="tests-hermetic-dirs"),
    pytest.param("sessions.file", "zzs/sessions.json", "zzs/sessions.json", "task-input", id="sessions-file"),
    pytest.param("locks.targets", [{"name": "n", "paths": ["zzl/**"]}], "zzl/x.txt", "locked", id="locks-targets"),
    pytest.param("state.dir", "zzst", "zzst/x.json", "state", id="state-dir"),  # R274e (13): the state folder had no row in the key map
])
def test_each_covered_profile_key_resolves_to_its_kind(key, value, sample, kind):
    """Catches: a folder named by a profile key that no owner row resolves, or that resolves to another kind."""
    import owners
    head, _, leaf = key.partition(".")
    profile = {head: {leaf: value}} if leaf else {head: value}
    assert owners.kind_of(sample, profile).name == kind

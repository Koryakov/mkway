"""engine/KEYS.md: one line per draft profile key of the port map (card MW-001, row E23)."""
import json
from pathlib import Path

from _keys_md import section_rows, unquote

REPO = Path(__file__).resolve().parents[1]
SCHEMA = REPO / "engine" / "profile.schema.json"

DRAFT_KEYS = [
    "test_roots", "derived.root", "derived.files", "card.id_pattern", "card.path_glob", "register.file",
    "rule.short_pattern", "rule.in_text_pattern", "owner_edit.name_pattern", "owner_edit.dirs",
    "owner_edit.card_globs", "open.owner_pattern", "open.count_pattern", "downstream.kinds", "downstream.universe",
    "downstream.change_list", "downstream.checklist", "downstream.chain", "downstream.delivered",
    "downstream.vocabulary", "locks.record", "locks.names", "locks.marker", "outbox.dir", "outbox.id_patterns_file",
    "outbox.checkers", "plan.always", "number_bases.bases", "number_bases.shapes", "customer_ids",
    "decision_search.ledger", "decision_search.log_file", "decision_search.cache_dir", "decision_search.noise_paths",
    "decision_search.ledger_id_prefixes", "decision_search.process_card", "decision_search.standing",
    "decision_search.source_aliases", "delete.generated_state", "bundle.root", "registration.file", "ledger.file",
    "ledger.parts_dir", "state.dir", "knowledge.files", "gates", "product_checks", "python.command",
    "ids.decision_row", "ids.rule_card", "ids.work_item", "ids.evidence", "locks.open_files", "user.settings_paths",
    "user.protected_hooks", "lock.rules.folder", "lock.rules.card_name_pattern", "lock.rules.guarded_files",
    "lock.rules.record_dirs", "lock.rules_code.folder", "lock.rules_code.whitelist_file", "lock.code.file",
    "freeze.pages", "freeze.folder_pattern", "handback.checkers", "cards.path", "cards.before_switch",
    "rule_source.folders", "rule_source.branch_check_dir", "evidence.store", "evidence.adapter_path",
    "golden.cases_file", "golden.report", "golden.fields", "ledger.columns",
]
NOW = "in schema now"
LATER = "later (stays a knot)"


def _leaves(node, prefix=""):
    """Leaf key paths declared in the schema (an object with no declared properties of its own is a leaf,
    unless it is a later group that must stay empty)."""
    props = node.get("properties")
    if props is None:
        return {prefix} if prefix else set()
    out = set()
    for name, child in props.items():
        path = f"{prefix}.{name}" if prefix else name
        if child.get("type") == "object" and child.get("properties") == {} and child.get("additionalProperties") is False:
            continue  # a later group: declared, empty
        out |= _leaves(child, path)
    return out


def test_keys_md_has_one_line_per_draft_key():
    """E23: 75 lines in map order, each «in schema now» (with the schema path it maps to) or «later (stays a knot)»
    with a reason; the «now» paths are exactly the schema's declared leaves."""
    assert len(DRAFT_KEYS) == 75
    rows = section_rows("Profile keys")
    assert [int(r[0]) for r in rows] == list(range(1, 76))
    assert [unquote(r[1]) for r in rows] == DRAFT_KEYS
    now_paths = set()
    for num, key, verdict, path, reason in rows:
        assert verdict in (NOW, LATER), (num, verdict)
        assert reason, num
        if verdict == NOW:
            now_paths.add(unquote(path))
        else:
            assert path in ("", "-"), num
    # changed by MW-002 (E19): the added keys that are in the schema now count too; only those the MW-002 order adds
    added = section_rows("Added keys")
    for key, verdict, path, _values, _reason in added:
        assert verdict in (NOW, LATER, "proposed", "no key"), (key, verdict)
        if verdict == NOW:
            now_paths.add(unquote(path))
    # changed by MW-003 (E32): the keys the MW-003 order adds are in the schema too
    assert {unquote(r[0]) for r in added if r[1] == NOW} == {
        "vcs", "ids.card_prefix", "gates.<name>.budget_seconds", "cards.owner_moves", "cards.approver",
        "register.columns", "locks.targets", "paths.docs", "paths.exempt", "test_env", "questions.files",
        "owner_ask.dir", "owner_ask.markers", "owner_ask.sources",  # changed by MW-007 (E1, E3): the ask gate's keys
        "agents.cap_minutes",  # changed by MW-004 (E16): the agent cap of the start block
        "rules.cards", "rules.test_for",  # changed by MW-021 (E3): the rule-card keys
        "deliverables.paths", "deliverables.require_base",  # changed by MW-020 (E2): the deliverables keys
        "commit.junk", "commit.data_patterns", "commit.max_file_kb",  # changed by MW-006 (E3): the commit gate's keys
        "tests.command", "gates.commit_tests.budget_seconds",  # changed by MW-005 (E5): the commit gate's keys
        "delete.max_backup_mb", "delete.sql_allowed",  # changed by MW-009 (E3): the delete gate's keys
        "gates.trip.min_calls", "gates.trip.share",  # changed by MW-012 (E20): the trip keys; schema path `gates`
        "owner_ask.max_open", "owner_ask.tool_allowed", "notify.command",  # changed by MW-014 (E19): the asks that do not stop the work
        "leads.escalate_hours", "leads.max_cards",  # changed by MW-017 (E20): the lead role's two keys
        "messaging.duplicate_window_hours", "messaging.dead_hours",  # changed by MW-018 (E14): the messaging keys
        "messaging.ack_reminder_minutes",
        "state.shared_dir",  # changed by MW-026: the opt-in shared state folder
        "lock_gate.git_builtins_extra",  # changed by MW-031: names added to the git built-in list
        "commit.message_prefix"}  # changed by MW-035: the prefix of the install commit message
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert now_paths == _leaves(schema)


def test_added_keys_and_decided_lines():
    """E22 (MW-002): `vcs` and `ids.card_prefix` are in schema now; the profile location is no key (by convention
    `<root>/mkway/profile.json`, or `--profile`); the decided line on an invalid profile is in KEYS.md. Changed by
    MW-003 (list item 1, R64): the line no longer exempts the profile file; the session is refused and the owner
    fixes the profile where no hook runs."""
    rows = {unquote(r[0]): r for r in section_rows("Added keys")}
    assert rows["vcs"][1:3] == [NOW, "`vcs`"]
    assert rows["ids.card_prefix"][1:3] == [NOW, "`ids.card_prefix`"]
    assert rows["gates.<name>.budget_seconds"][1:3] == [NOW, "`gates`"]
    location = rows["profile location"]
    assert location[1] == "no key"
    assert "`<root>/mkway/profile.json`" in location[3] and "`--profile <path>`" in location[3]
    text = (REPO / "engine" / "KEYS.md").read_text(encoding="utf-8")
    flat = " ".join(text.split())
    assert ("Decided (R64, 10.11): while the profile is invalid, every edit and shell call of a session is refused; "
            "the refusal carries the schema error (key path and message) so the session can tell the owner exactly "
            "what to fix; the owner fixes it in their editor or terminal, where no hook runs; `mkway check` prints "
            "the same error.") in flat
    assert "stay exempt" not in flat

"""Card MW-059: the topology refusal of a lead's order to a session that holds no card names the new-session route.
The gate is unchanged; only the text differs. Layers: the text as a table, the real hook. Synthetic names only."""
import pytest

from _hook_driver import decision, install_project
import messages

LEAD, FREE, BUILDER = "L1", "n1", "b1"
CLI = "python mkway/engine/mkway.py"
NEW_ROUTE = "holds no card. Start a new builder session with the order as its first prompt (mkcl), one card = one session."
OLD_TEXT = "a lead writes to another lead or to a builder of a card it ordered"


def _refusal_text(target_role, kind="order"):
    with pytest.raises(messages.MessageError) as caught:
        messages._topology("L1", messages.Role("lead"), "T1", target_role, kind)
    assert caught.value.reason == "message-topology"
    return caught.value.message


TABLE = [
    # (target role, kind, the text holds the new route)
    (messages.Role("none"), "order", True),
    (messages.Role("none", None, "CARD-9"), "order", False),  # holds a card, not ordered by a lead of ours
    (messages.Role("builder", "L2", "CARD-9"), "order", False),  # a builder of another lead
    (messages.Role("none"), "question", False),  # only an order names the new-session route
]


def _text_ok(text, route):
    """True when the refusal text is the new-route text for a route row, and the old text without the route otherwise."""
    if route:
        return text == f"order refused: T1 {NEW_ROUTE}"
    return OLD_TEXT in text and "mkcl" not in text


@pytest.mark.parametrize("role, kind, route", TABLE)
def test_the_refusal_text_for_a_target_that_holds_no_card(role, kind, route):
    """Catches: an order to a target with no card refused without the new-session route, or another refusal whose text changed (E1)."""
    text = _refusal_text(role, kind)
    assert _text_ok(text, route), text


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    p = install_project(tmp_path_factory.mktemp("topology"))
    for session in (LEAD, FREE):
        decision(p.fire("SessionStart", session))
    p.session_shell(LEAD, f"{CLI} lead register")
    p.write("msg/body.txt", "do this\n")
    return p


def test_an_order_to_an_idle_session_is_denied_with_the_new_route_through_the_real_hook(proj):
    """Catches: an order to a session with no card that the real hook does not refuse, or a refusal whose text lacks the new builder session route (E2)."""
    proc = proj.session_shell(LEAD, f'{CLI} send --to {FREE} --kind order --text "do this"', expect_ok=False)
    assert proc.returncode != 0
    out = proc.stdout + proc.stderr
    assert "message-topology" in out
    assert f"order refused: {FREE} {NEW_ROUTE}" in out

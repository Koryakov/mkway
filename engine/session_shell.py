"""The shell side shared by the session family's gates (card MW-066): maps a pure `core_session.Verdict` to the gate
interface's verdict. allow -> allow, refuse -> refuse, allow-with-line -> warn."""
from __future__ import annotations

import core_session
import gate


def verdict(decided: core_session.Verdict) -> gate.Verdict:
    if decided.kind == core_session.REFUSE:
        return gate.refuse(decided.reason, decided.text)
    if decided.kind == core_session.ALLOW_LINE:
        return gate.warn(decided.reason, decided.text)
    return gate.allow()

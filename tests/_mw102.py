"""Shared helpers for the MW-102 tests (the orderer commits the verdict file of a card it ordered). Not a test module.
Synthetic sessions, agents, files and names only; built on the MW-080 and MW-100 helpers.

`verdict_root` is the MW-080 git task root whose card CARD-001 is ordered by the session `LEAD`, with one fresh reader run
(session `reader`, agent `a1`). `add` writes rows through the real `verdict add` (in process). `decide` is the real commit gate
(`gate_commit.check`) for a call of a session: (reason id or `allow`, the refusal text)."""
import _mw080 as w
import _mw100 as m
import register
from _engine import gate_call

LEAD, READER = m.LEAD, m.READER
CARD, N1, N2, N3, B1 = w.CARD, w.N1, w.N2, w.N3, w.B1
REL = w.VERDICT_REL
MESSAGE = f"git commit -m '{CARD} the verdict file'"
NAMED = f"{MESSAGE} -- {REL}"
HEADER = "| Node | Verdict | Reason | By |\n|---|---|---|---|\n"
EDITED = "an edited reason"


def verdict_root(tmp_path, **kw):
    root = m.lead_root(tmp_path, **kw)
    w.reader(root, READER, "a1")
    return root


def add(root, *nodes):
    """Rows written by the real command; the call must be allowed."""
    assert w.apply(root, READER, list(nodes), "true", "one clause, one case").allowed


def stage(root):
    w.git(root, "add", "-f", "--", REL)


def save(root):
    """The verdict file committed with git directly (the test's own step, no gate)."""
    stage(root)
    w.git(root, "commit", "-q", "-m", f"{CARD} the verdict file", when=-1000)


def text(root) -> str:
    return w.verdict_text(root)


def put(root, content: str):
    (root / REL).parent.mkdir(parents=True, exist_ok=True)
    (root / REL).write_text(content, encoding="utf-8")


def typed(root, *nodes, header=True):
    """Rows typed by hand: no record in the proof file stands behind them."""
    put(root, (HEADER if header else "") + "".join(f"| {n} | true | typed by hand | session:{READER} |\n" for n in nodes))


def close_card(root):
    profile = w.profile_of(root)

    def mutate(table):
        register.find(table, CARD)["status"] = "closed"
        return table
    register.write(root, profile, mutate)


def decide(root, command=MESSAGE, session=LEAD):
    """The commit gate's verdict for a Bash call of `session`: (reason id or `allow`, the refusal text)."""
    import gate_commit
    got = gate_call(gate_commit.check, root, tool="Bash", tool_input={"command": command}, session=session)
    return (got.reason_id, got.message) if got.kind == "refuse" else ("allow", "")

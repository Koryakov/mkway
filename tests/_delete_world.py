"""A virtual task root for the delete table tests (card MW-064). Not a test module. No disk, no git, no clock: the world
is a set of repo paths, a set of tracked paths and a map of changed paths; `judge` reads a shell command with the gate's
reader (root `None`: every `cd` target counts as a folder that exists) and answers each `Need` of the pure core from
that world, the way the shell answers it from the real tree. The path model is the engine's own `helpers.norm` on a
posix root, so `..`, an absolute path and the home folder are placed as they are on a real root."""
import _engine  # noqa: F401  (puts engine/ on the path)
import core_delete as core
import gate_delete
import helpers

ROOT = "/task"
HOME = "/home/u"
FILES = frozenset({"a.txt", "b.txt", "d", "d/b.txt", "d/c.txt", "mkway", "mkway/state", "mkway/state/deletes.jsonl"})
STATE = "mkway/state"
LIST_FIX = "mkway delete --list <file>"


def norm(path):
    return helpers.norm(path, ROOT, top_prefix="", home=HOME)


def _lines(paths, table):
    hit = [(p, code) for p, code in sorted(table.items())
           if not paths or any(q == "." or p == q or p.startswith(q + "/") for q in paths)]
    return hit


def judge(command, tool="Bash", *, files=FILES, sql_allowed=False, vcs_git=False, tracked=(), changed=None,
          git_failure=None, start=""):
    """The core's decision for one shell command in the virtual world. `tracked`: the tracked repo paths; `changed`:
    {repo path: two-letter porcelain code}; `git_failure`: the words of a git read that fails, for every git read."""
    shell = "powershell" if tool == "PowerShell" else "bash"
    steps = gate_delete.read(command, shell=shell, start=start, root=None)
    facts = core.Facts(sql_allowed=sql_allowed, state=STATE, vcs_git=vcs_git)
    changed = changed or {}
    for _ in range(200):
        try:
            return core.decide(steps, facts)
        except core.Need as need:
            if need.kind == "norm":
                answer = norm(need.key)
            elif need.kind == "exists":
                answer = need.key in files
            elif need.kind == "status":
                answer = (git_failure, tuple(f"{code} {p}" for p, code in _lines(need.key, changed)))
            elif need.kind == "tracked":
                answer = (git_failure, tuple(p for p in sorted(tracked) if p == need.key or p.startswith(need.key + "/")))
            else:
                raise AssertionError(f"the world does not know the fact {need.kind!r}")
            facts.answers[(need.kind, need.key)] = answer
    raise AssertionError("the core kept asking for facts")


def reason(decision):
    return decision.verdict.reason if decision.verdict.kind == "refuse" else "allow"

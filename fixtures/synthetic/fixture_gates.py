"""Synthetic fixture gates for the dispatcher tests (card MW-002). Not shipped as engine gates; a test that needs them
names them in its own manifest entries."""
import sys
import time

from gate import allow, refuse, warn


def always_refuse(event, ctx):
    return refuse("fixture-refuse", "fixture gate: always refuses")


def always_warn(event, ctx):
    return warn("fixture-warn", "fixture gate: always warns")


def raises(event, ctx):
    raise RuntimeError("fixture gate: planted failure")


def always_log(event, ctx):  # card MW-003 list item 5: a `log` verdict
    import gate
    return gate.log("fixture-log", "fixture gate: always logs")


def warn_once(event, ctx):
    target = (ctx.tool_input or {}).get("file_path", "")
    if ctx.once([target]):
        return warn("fixture-once", f"fixture gate: first time for {target}")
    return allow()


def slow_warn(event, ctx):
    time.sleep(0.05)
    return warn("fixture-slow", f"fixture gate: budget={ctx.budget_seconds}")


def undeclared(event, ctx):
    return refuse("not-declared", "fixture gate: a reason id the entry does not declare")


def exits(event, ctx):
    sys.exit(0)


def refuse_once(event, ctx):
    if ctx.once(["fixture-target"]):
        return refuse("fixture-refuse", "fixture gate: refuses the first time")
    return allow()

"""Synthetic gate for the watch mode and trip tests (card MW-012). Not shipped as an engine gate."""
from gate import allow, refuse


def refuse_if_bad(event, ctx):
    """Refuses a target whose path holds `bad`; allows every other call."""
    target = (ctx.tool_input or {}).get("file_path", "")
    if "bad" in target:
        return refuse("fixture-refuse", "fixture gate: refuses a bad target")
    return allow()

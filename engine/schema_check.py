"""Check a branch profile against engine/profile.schema.json. Standard library only.

Supported schema words: type, required, properties, additionalProperties (bool or schema), items, minLength,
minItems, maxItems, exclusiveMinimum (a number must be greater than it),
enum, pattern (re.search), format ("regex": compiles; "relative-path": no drive, no leading slash, no `..` part; "absolute-path": a drive or a leading slash, no `..` part).
Each error is `<key path>: <problem>`; the key path uses dots for keys and [i] for list items.

Usage: python engine/schema_check.py <profile.json>   (exit 0 = valid, 1 = errors)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCHEMA_FILE = Path(__file__).resolve().with_name("profile.schema.json")
_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}
_DRIVE = re.compile(r"^[A-Za-z]:")


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _format_error(fmt: str, value: str):
    if fmt == "regex":
        try:
            re.compile(value)
        except re.error:
            return "not a valid regex"
    elif fmt == "absolute-path":  # MW-026: a drive or a leading slash, no `..` part
        parts = re.split(r"[/\\]", value)
        if not (re.match(r"^[A-Za-z]:[\\/]", value) or value[:1] in ("/", "\\")) or ".." in parts:
            return "not an absolute path"
    elif fmt == "relative-path":
        parts = re.split(r"[/\\]", value)
        if not value or _DRIVE.match(value) or value[0] in "/\\" or ".." in parts:
            return "not a relative path inside the repository"
    return None


def _check(value, schema: dict, path: str, errors: list) -> None:
    where = path or "(profile)"
    types = schema.get("type")
    if types is not None:
        names = types if isinstance(types, list) else [types]
        if not any(_TYPES[t](value) for t in names):
            errors.append(f"{where}: expected {' or '.join(names)}")
            return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where}: not one of {', '.join(map(str, schema['enum']))}")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and "exclusiveMinimum" in schema \
            and value <= schema["exclusiveMinimum"]:
        errors.append(f"{where}: must be greater than {schema['exclusiveMinimum']}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{where}: empty")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{where}: does not match {schema['pattern']}")
        if "format" in schema:
            problem = _format_error(schema["format"], value)
            if problem:
                errors.append(f"{where}: {problem}")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{_join(path, key)}: required")
        extra = schema.get("additionalProperties", True)
        for key, item in value.items():
            sub = _join(path, key)
            if key in props:
                _check(item, props[key], sub, errors)
            elif extra is False:
                errors.append(f"{sub}: not allowed here")
            elif isinstance(extra, dict):
                _check(item, extra, sub, errors)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{where}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{where}: more than {schema['maxItems']} items")
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for i, item in enumerate(value):
            _check(item, schema["items"], f"{path}[{i}]", errors)


def load_schema(path=SCHEMA_FILE) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check(profile, schema=None) -> list:
    """All errors of a profile (an empty list means valid)."""
    errors: list = []
    _check(profile, schema if schema is not None else load_schema(), "", errors)
    _hold_flag(profile, errors)
    return errors


BUILT_IN_TARGETS = ("engine", "lock", "profile", "hooks", "locks", "gitignore", "gitattributes", "register", "state",
                    "upgrade")  # `upgrade`: MW-105 (R260b 2)


def _hold_flag(profile, errors: list) -> None:
    """`open_by_default` is for profile lock targets only: a built-in target name with the flag is an error (MW-010).
    The names are those of `locks.built_in` (a test keeps the two lists equal)."""
    locks = profile.get("locks") if isinstance(profile, dict) else None
    targets = locks.get("targets") if isinstance(locks, dict) else None
    for i, t in enumerate(targets if isinstance(targets, list) else []):
        if isinstance(t, dict) and t.get("open_by_default") is True and t.get("name") in BUILT_IN_TARGETS:
            errors.append(f"locks.targets[{i}]: open_by_default is refused on the built-in target {t['name']!r}; "
                          "a built-in target is never open by default")


def check_file(path, schema=None) -> list:
    try:
        profile = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"(profile): not valid JSON (line {exc.lineno})"]
    return check(profile, schema)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: schema_check.py <profile.json>", file=sys.stderr)
        return 2
    errors = check_file(argv[0])
    for e in errors:
        print(e)
    print(f"profile check: {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

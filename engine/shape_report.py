"""The one-off report of card MW-073: every existing test function that breaks a shape rule S1 to S7, counted per rule and
per file, for the later re-judging card. It is not a gate and writes nothing. Run from the task root:
`python engine/shape_report.py [folder]` (the folder defaults to `tests`)."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, NamedTuple

import core_shape


class Report(NamedTuple):
    tests: int  # the test functions judged
    by_rule: Dict[str, int]  # breaches per rule, a rule with none is left out
    by_file: Dict[str, int]  # breaches per file, a file with none is left out


def scan(root: Path, folder: str = "tests") -> Report:
    """Judge every `test_*.py` under `root/folder` as if the whole file were new."""
    root = Path(root)
    sources = tuple(core_shape.Source(p.relative_to(root).as_posix(), p.read_text(encoding="utf-8", errors="replace"))
                    for p in sorted((root / folder).rglob("test_*.py")))
    verdict = core_shape.decide(core_shape.Facts(sources))
    by_rule, by_file = {}, {}
    for b in verdict.breaches:
        by_rule[b.rule] = by_rule.get(b.rule, 0) + 1
        by_file[b.file] = by_file.get(b.file, 0) + 1
    return Report(verdict.judged, by_rule, by_file)


def lines(report: Report) -> list:
    out = [f"tests judged: {report.tests}", f"breaches: {sum(report.by_rule.values())}"]
    out += [f"{rule}: {report.by_rule.get(rule, 0)}" for rule in core_shape.RULES]
    out += [f"{name}: {n}" for name, n in sorted(report.by_file.items(), key=lambda item: (-item[1], item[0]))]
    return out


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    print("\n".join(lines(scan(Path.cwd(), args[0] if args else "tests"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

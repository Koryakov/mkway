"""Synthetic fixture (card MW-002, fix check 2 L2): a gate module that exits while it is imported."""
import sys

sys.exit(0)


def gate(event, ctx):  # never reached
    raise AssertionError("not reached")

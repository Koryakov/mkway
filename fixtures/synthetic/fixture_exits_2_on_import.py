"""Synthetic fixture (card MW-002, fix check 3): a gate module that exits with code 2 while it is imported."""
import sys

sys.exit(2)


def gate(event, ctx):  # never reached
    raise AssertionError("not reached")

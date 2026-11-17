"""Shell tests (card MW-052; the ruling of 2026-11-12): they read facts from real git and keep the 20 s per-test cap of
MW-047. The cap covers the test itself; a session fixture that builds the prepared repositories is not counted."""
import time

import pytest

CAP_SECONDS = 20.0


@pytest.fixture(autouse=True)
def _a_shell_test_takes_under_20_seconds():
    started = time.perf_counter()
    yield
    took = time.perf_counter() - started
    assert took < CAP_SECONDS, f"a shell test must run under {CAP_SECONDS:g} s; this one took {took:.1f} s"

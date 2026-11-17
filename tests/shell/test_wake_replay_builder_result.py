"""Card MW-078, the replay row: the real case of the card. A builder wrote a `result` row into its lead's inbox with
`mkway send`; the row was in the inbox, there was no ping, and the lead stayed idle. Here the lead's real waiter process
(the shared state folder is set, as in that task's profile) is woken by the very row the real `send` wrote. Synthetic
session ids and text only."""
import pytest

import _wake_world as wake
from _mw018 import id_of, send
import sessions


@pytest.fixture
def pool():
    processes = wake.Pool()
    yield processes
    processes.kill_all()


def test_a_builders_result_row_wakes_the_leads_waiter_with_that_rows_line(tmp_path, pool):
    """Catches: the replay, a result row sitting in a lead's inbox while its session is idle and nothing wakes it."""
    shared = tmp_path / "shared"
    root = wake.waiter_root(tmp_path, shared=shared)
    wake.make_lead(root, "lead-1")
    wake.make_builder(root, "lead-1", "build-1")
    sessions.append(shared, "lead-1", root)
    sessions.append(shared, "build-1", root)
    proc = pool.start(root, "lead-1")
    assert wake.wait_for(lambda: wake.pid_text(root, "lead-1") != "")
    code, out, err = send(root, "build-1", "lead-1", "result", "the builder result is ready")
    row_id = id_of(out)
    expected = (f"{row_id} result from build-1: the builder result is ready "
                f"(`mkway inbox {row_id}`, then `mkway ack {row_id}`)\n")
    assert (code, wake.finish(proc)) == (0, (2, "", expected))

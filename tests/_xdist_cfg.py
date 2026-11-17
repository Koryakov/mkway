"""The parallel run of the suite (card MW-083, decisions: R199, R200). Not a test module; pure, standard library only.

`tests/conftest.py` calls these from its xdist hooks: the number of workers that `-n auto` starts, and the hand-over of the
run's seed from the controller to every worker (workers that took their own clock seed would shuffle `tests/core` in
different orders, and xdist refuses a run whose workers collect in different orders)."""

ENV_NAME = "MKWAY_TEST_WORKERS"
BAD_ENV_TEXT = "MKWAY_TEST_WORKERS must be a whole number above 0"
SEED_KEY = "hermetic_seed"


def worker_count(cores, env_text):
    """The number of workers: the whole number in `env_text` (the text of `MKWAY_TEST_WORKERS`, None when unset), else half
    of `cores` (None when the machine names no count), never below one. A text that is not a whole number above 0
    raises ValueError."""
    if env_text is not None:
        if not (env_text.isascii() and env_text.isdigit() and int(env_text) > 0):
            raise ValueError(BAD_ENV_TEXT)
        return int(env_text)
    return max(1, (cores or 1) // 2)


def put_seed(workerinput, seed):
    """Hand `seed` to a worker: the controller calls this on the `workerinput` of each worker it starts."""
    workerinput[SEED_KEY] = int(seed)


def handed_seed(config):
    """The seed the controller handed to this worker, or None (a serial run, the controller, a worker with no seed)."""
    return getattr(config, "workerinput", {}).get(SEED_KEY)

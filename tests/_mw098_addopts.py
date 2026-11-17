"""Helper of card MW-098: the token list of the addopts setting with the one allowed pair `-m "not perf"` dropped."""


def drop_allowed_pair(tokens):
    rest = list(tokens)
    for i in range(len(rest) - 1):  # drop the one allowed pair: -m "not perf"
        if rest[i] == "-m" and rest[i + 1] == "not perf":
            del rest[i:i + 2]
            break
    return rest

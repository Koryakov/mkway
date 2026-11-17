"""Card MW-094 helper: a coordinated forge of one card's status in the register and its seal (the decided limit of R19a),
used by the start-line tests. Synthetic task roots only."""
import hashlib


def forge_status(root, card_id, was, now):
    """A coordinated forge (the decided limit of R19a): the register and its seal written together, no record."""
    reg = root / "mkway" / "cards" / "REGISTER.md"
    text = reg.read_text(encoding="utf-8")
    line = next(x for x in text.splitlines() if x.startswith(f"| {card_id} |"))
    reg.write_bytes(text.replace(line, line.replace(f"| {was} |", f"| {now} |")).encode("utf-8"))
    (root / "mkway" / "state" / "register.sha").write_text(hashlib.sha256(reg.read_bytes()).hexdigest(),
                                                          encoding="utf-8")

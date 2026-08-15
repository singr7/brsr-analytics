from __future__ import annotations

import hashlib
import math


def hash_embedding(text: str, dimensions: int = 1024) -> list[float]:
    """Deterministic offline embedding used by CI and as the explicit local model."""
    values = [0.0] * dimensions
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        values[index] += -1.0 if digest[4] & 1 else 1.0
    norm = math.sqrt(sum(value * value for value in values))
    return [value / norm for value in values] if norm else values

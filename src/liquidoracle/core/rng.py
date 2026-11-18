"""Random generators from an explicit Seed (AD-15).

Every random unit gets its own generator, so one Wallet's draws never depend on which Wallets
came before it. Python's `hash()`, the `random` module and numpy's global state are never used.
"""

from __future__ import annotations

from hashlib import sha256

import numpy as np

# A purpose's code must never change: changing it changes every stored result (AD-15).
PURPOSES = {"skilltest": 1}


def spawn_key(purpose: str, unit_id: str) -> tuple[int, int]:
    """AD-15: (fixed code of the purpose, first 8 bytes of sha256 of the id as an integer)."""
    if purpose not in PURPOSES:
        raise ValueError(f"unknown random purpose {purpose!r}")
    return PURPOSES[purpose], int.from_bytes(sha256(unit_id.encode("utf-8")).digest()[:8], "big")


def generator(seed: int, purpose: str, unit_id: str) -> np.random.Generator:
    """The generator for one random unit: SeedSequence(seed, spawn_key=...) into PCG64 (AD-15)."""
    sequence = np.random.SeedSequence(seed, spawn_key=spawn_key(purpose, unit_id))
    return np.random.Generator(np.random.PCG64(sequence))

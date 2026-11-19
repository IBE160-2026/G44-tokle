"""Typed errors raised by `data/` (Consistency Conventions › Errors).

`services/` turns them into the messages in EXPERIENCE.md; pages never show a raw exception.
Story 2.1 adds `PolymarketUnavailable` and `PolymarketBadRequest` here.
"""

from __future__ import annotations


class NotAvailableOffline(LookupError):
    """Offline Mode was asked for a Wallet or Market outside the Sample Dataset (FR-14)."""

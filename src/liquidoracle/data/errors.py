"""Typed errors raised by `data/` (Consistency Conventions › Errors).

`services/` turns them into the messages in EXPERIENCE.md; pages never show a raw exception.
"""

from __future__ import annotations


class NotAvailableOffline(LookupError):
    """Offline Mode was asked for a Wallet or Market outside the Sample Dataset (FR-14)."""


class PolymarketUnavailable(RuntimeError):
    """Polymarket did not answer usefully after the one retry policy (AD-3, FR-2).

    Raised after the third failed try, at once for a `Retry-After` over 60 seconds, and for
    an answer the client cannot read. A job that meets it stops as `stopped`, which can resume (AD-5).
    """


class PolymarketBadRequest(RuntimeError):
    """Polymarket refused the request with a 4xx that is not retried (AD-3). It is logged."""

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


class ProtocolContractAddress(PolymarketBadRequest):
    """A 400 "protocol contract address": the address is one of Polymarket's own contracts (AD-9).

    The Scan (Epic 4) drops such addresses as candidates instead of counting them as not fully read.
    """

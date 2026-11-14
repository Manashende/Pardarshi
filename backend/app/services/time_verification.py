"""
Module 4 / Algorithm C — verified time-lock, cross-checked against
multiple independent NTP sources to prevent a single spoofed clock from
enabling early access.

Design note: real networks (including, as you've seen, college networks)
sometimes can't reach external NTP servers at all. A system that
hard-fails whenever NTP is unreachable would be unusable exactly when
it needs to work. So this degrades in clearly-labeled stages instead of
silently pretending everything is always fully cross-verified:

  CROSS_VERIFIED        — 2+ independent sources agreed within tolerance
  SINGLE_SOURCE          — only 1 source reachable
  UNVERIFIED_LOCAL       — no source reachable, fell back to system clock
  DISAGREEMENT_FLAGGED   — 2+ sources reachable but disagree too much
                            (possible spoofing) — NOT the same as
                            CROSS_VERIFIED even though 2+ sources answered

Every verification_level should be recorded in the ledger by the caller.
Document this degradation behavior explicitly in your report — it's a
real design decision, not something to gloss over.
"""
import time
import enum
from dataclasses import dataclass
from typing import List, Optional

import ntplib


class VerificationLevel(str, enum.Enum):
    CROSS_VERIFIED = "CROSS_VERIFIED"
    SINGLE_SOURCE = "SINGLE_SOURCE"
    UNVERIFIED_LOCAL = "UNVERIFIED_LOCAL"
    DISAGREEMENT_FLAGGED = "DISAGREEMENT_FLAGGED"


@dataclass
class VerifiedTime:
    epoch: float
    verification_level: VerificationLevel
    sources_used: List[str]
    max_disagreement_seconds: Optional[float]


def _query_single_ntp(server: str, timeout: float = 3.0) -> Optional[float]:
    try:
        client = ntplib.NTPClient()
        response = client.request(server, version=3, timeout=timeout)
        return response.tx_time
    except Exception:
        return None


def get_verified_time(servers: List[str], max_disagreement_seconds: float = 5.0) -> VerifiedTime:
    results = {}
    for server in servers:
        t = _query_single_ntp(server)
        if t is not None:
            results[server] = t

    if len(results) >= 2:
        values = list(results.values())
        max_disagreement = max(values) - min(values)
        if max_disagreement > max_disagreement_seconds:
            return VerifiedTime(
                epoch=min(values),  # never let a spoofed-forward clock help unlock early
                verification_level=VerificationLevel.DISAGREEMENT_FLAGGED,
                sources_used=list(results.keys()),
                max_disagreement_seconds=max_disagreement,
            )
        avg_time = sum(values) / len(values)
        return VerifiedTime(
            epoch=avg_time,
            verification_level=VerificationLevel.CROSS_VERIFIED,
            sources_used=list(results.keys()),
            max_disagreement_seconds=max_disagreement,
        )

    if len(results) == 1:
        server, t = next(iter(results.items()))
        return VerifiedTime(
            epoch=t,
            verification_level=VerificationLevel.SINGLE_SOURCE,
            sources_used=[server],
            max_disagreement_seconds=None,
        )

    return VerifiedTime(
        epoch=time.time(),
        verification_level=VerificationLevel.UNVERIFIED_LOCAL,
        sources_used=[],
        max_disagreement_seconds=None,
    )


def is_acceptable_for_standard_unlock(level: VerificationLevel) -> bool:
    """
    Only CROSS_VERIFIED is trustworthy enough for the STANDARD unlock
    path. Everything else must route to the higher-threshold OVERRIDE
    path instead.
    """
    return level == VerificationLevel.CROSS_VERIFIED
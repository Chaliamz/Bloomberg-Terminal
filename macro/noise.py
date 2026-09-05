"""Noise filter (spec section 26).

One question decides everything: does this change what the market previously
believed?  Items that do not are downgraded regardless of how loud they are.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from .types import Category, Tier, iso

CLICKBAIT = (
    "you won't believe", "shocking", "this is why", "here's why", "explodes",
    "plunges to", "skyrockets", "crashes as", "insider reveals", "secret",
    "must see", "warns of collapse", "about to", "could be about to",
    "bombshell", "stunning", "massive move incoming",
)

OPINION_MARKERS = (
    "i think", "we believe", "in my view", "analysts say", "experts warn",
    "could", "might", "may", "reportedly", "rumor", "rumour", "speculation",
    "sources say", "it appears", "seems to",
)

# Verbs that indicate genuinely new information rather than restatement.
NEW_INFO_MARKERS = (
    "announced", "raised", "cut", "lowered", "voted", "declared", "signed",
    "released", "reported actual", "revised", "resigned", "intervened",
    "suspended", "sanctioned", "defaulted", "downgraded", "upgraded",
    "filed", "confirmed", "unexpectedly",
)


@dataclass(frozen=True)
class NoiseVerdict:
    keep: bool
    penalty: float               # 0..1 multiplier applied to the priority score
    reasons: tuple[str, ...]
    changes_expectations: bool | None
    category: Category = Category.INTERPRETATION
    ok: bool = True

    def render(self) -> str:
        head = "KEEP" if self.keep else "SUPPRESS"
        return f"{head} (x{self.penalty:.2f}) - " + "; ".join(self.reasons)


def _tokens(text: str) -> set[str]:
    return set(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())


def jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def filter_item(
    headline: str,
    *,
    tier: Tier = Tier.UNKNOWN,
    seen_headlines: list[str] | None = None,
    published_at: datetime | None = None,
    now: datetime | None = None,
    changes_expectations: bool | None = None,
    duplicate_threshold: float = 0.72,
    stale_after_hours: float = 36.0,
) -> NoiseVerdict:
    reasons: list[str] = []
    penalty = 1.0
    keep = True
    low = headline.lower()

    if seen_headlines:
        for prior in seen_headlines:
            sim = jaccard(headline, prior)
            if sim >= duplicate_threshold:
                reasons.append(f"near-duplicate of an item already seen (similarity {sim:.2f})")
                return NoiseVerdict(False, 0.0, tuple(reasons), changes_expectations)

    if any(p in low for p in CLICKBAIT):
        penalty *= 0.35
        reasons.append("clickbait phrasing")

    opinion_hits = [m for m in OPINION_MARKERS if m in low]
    new_hits = [m for m in NEW_INFO_MARKERS if m in low]
    if opinion_hits and not new_hits:
        penalty *= 0.5
        reasons.append(f"opinion/speculation framing with no new-information verb ({opinion_hits[0]})")
    if new_hits:
        reasons.append(f"contains a new-information verb ('{new_hits[0]}')")

    if tier is Tier.SOCIAL:
        penalty *= 0.45
        reasons.append("Tier 4 source: cannot be treated as confirmed")
    elif tier is Tier.UNKNOWN:
        penalty *= 0.6
        reasons.append("unclassified source")

    now = now or datetime.now(published_at.tzinfo if published_at else None)
    if published_at is not None:
        try:
            age_h = (now - published_at).total_seconds() / 3600.0
        except TypeError:
            age_h = None
            reasons.append("timezone-naive/aware mismatch: age not computed")
        if age_h is not None and age_h > stale_after_hours:
            penalty *= 0.3
            reasons.append(f"published {age_h:.0f}h ago ({iso(published_at)}): old news resurfacing")

    if changes_expectations is False:
        penalty *= 0.25
        reasons.append(
            "does not change what the market already believed: background, not signal"
        )
        keep = penalty > 0.15
    elif changes_expectations is True:
        penalty = min(1.0, penalty * 1.4)
        reasons.append("changes the prior distribution: this is the category that matters")
    else:
        reasons.append(
            "expectation impact not asserted: cannot rank this against priced-in items"
        )

    if penalty < 0.2:
        keep = False

    if not reasons:
        reasons.append("no noise markers found")

    return NoiseVerdict(keep, round(penalty, 3), tuple(reasons), changes_expectations)


__all__ = ["CLICKBAIT", "NEW_INFO_MARKERS", "NoiseVerdict", "OPINION_MARKERS",
           "filter_item", "jaccard"]

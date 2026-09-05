"""Source hierarchy and confirmation engine (spec sections 14 and 15)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import urlparse

from .scoring import credibility
from .types import Category, SourceRef, Tier, Verification, iso, utcnow

# Domain -> tier.  Primary means the institution that *creates* the information,
# not one that reports it accurately.  Matching is on the registrable suffix so
# subdomains inherit.
TIER1_DOMAINS = {
    "federalreserve.gov", "bls.gov", "bea.gov", "census.gov", "treasury.gov",
    "treasurydirect.gov", "dol.gov", "eia.gov", "sec.gov", "cftc.gov",
    "whitehouse.gov", "congress.gov", "newyorkfed.org", "ecb.europa.eu",
    "europa.eu", "ec.europa.eu", "destatis.de", "insee.fr", "istat.it",
    "bankofengland.co.uk", "ons.gov.uk", "gov.uk", "boj.or.jp", "mof.go.jp",
    "stat.go.jp", "mhlw.go.jp", "pbc.gov.cn", "stats.gov.cn", "customs.gov.cn",
    "bankofcanada.ca", "statcan.gc.ca", "rba.gov.au", "abs.gov.au",
    "rbnz.govt.nz", "snb.ch", "imf.org", "bis.org", "worldbank.org",
    "opec.org", "iea.org", "ismworld.org", "conference-board.org",
}
TIER2_DOMAINS = {
    "bloomberg.com", "reuters.com", "ft.com", "wsj.com", "cnbc.com",
    "economist.com", "barrons.com", "marketwatch.com", "nikkei.com",
    "handelsblatt.com", "lesechos.fr", "scmp.com", "cmegroup.com", "ice.com",
    "nasdaq.com", "nyse.com", "lseg.com", "eurex.com", "apnews.com",
    "afp.com", "dowjones.com",
}
TIER4_DOMAINS = {
    "x.com", "twitter.com", "t.me", "telegram.org", "reddit.com",
    "substack.com", "medium.com", "discord.com", "4chan.org", "tradingview.com",
    "seekingalpha.com", "youtube.com",
}


def classify_domain(url_or_name: str) -> Tier:
    host = url_or_name.strip().lower()
    if "://" in host or host.startswith("www."):
        host = urlparse(host if "://" in host else "https://" + host).netloc
    host = host.split(":")[0].removeprefix("www.")
    if not host:
        return Tier.UNKNOWN
    parts = host.split(".")
    suffixes = {".".join(parts[i:]) for i in range(len(parts))}
    if suffixes & TIER1_DOMAINS:
        return Tier.PRIMARY
    if suffixes & TIER2_DOMAINS:
        return Tier.INSTITUTIONAL
    if suffixes & TIER4_DOMAINS:
        return Tier.SOCIAL
    if host.endswith(".gov") or host.endswith(".gov.uk") or host.endswith(".go.jp"):
        return Tier.PRIMARY
    return Tier.UNKNOWN


def make_source(
    name: str, url: str | None = None, published_at: datetime | None = None,
    is_primary_document: bool = False,
) -> SourceRef:
    tier = classify_domain(url or name)
    return SourceRef(
        name=name, tier=tier, url=url, published_at=published_at,
        retrieved_at=utcnow(), is_primary_document=is_primary_document,
    )


# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfirmationResult:
    verification: Verification
    credibility_score: float
    best_tier: Tier
    independent_sources: int
    primary_source: SourceRef | None
    earliest_publication: datetime | None
    misinformation_flags: tuple[str, ...]
    required_actions: tuple[str, ...]
    label: str
    category: Category = Category.FACT
    ok: bool = True

    def render(self) -> str:
        flags = "".join(f"\n    ! {f}" for f in self.misinformation_flags)
        acts = "".join(f"\n    > {a}" for a in self.required_actions)
        return (
            f"{self.label} | credibility {self.credibility_score:.0f}/100 | "
            f"{self.independent_sources} independent source(s), best "
            f"{self.best_tier.label}{flags}{acts}"
        )


def _norm(text: str) -> set[str]:
    return set(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())


def confirm(
    claim: str,
    sources: list[SourceRef],
    *,
    claim_first_seen: datetime | None = None,
    conflicts_with_primary: bool = False,
    market_reaction_contradicts: bool = False,
    known_unreliable: set[str] | None = None,
) -> ConfirmationResult:
    """Assess how well a claim is sourced, and flag misinformation patterns."""
    known_unreliable = known_unreliable or set()
    flags: list[str] = []
    actions: list[str] = []

    if not sources:
        return ConfirmationResult(
            verification=Verification.UNCONFIRMED,
            credibility_score=credibility(Tier.UNKNOWN, Verification.UNCONFIRMED),
            best_tier=Tier.UNKNOWN, independent_sources=0, primary_source=None,
            earliest_publication=None,
            misinformation_flags=("no source attached to the claim at all",),
            required_actions=(
                "Locate the issuing institution's own publication before acting.",
            ),
            label="UNCONFIRMED - REQUIRES VERIFICATION",
        )

    best_tier = min((s.tier for s in sources), key=lambda t: t.value)
    primary = next(
        (s for s in sources if s.tier is Tier.PRIMARY or s.is_primary_document), None
    )

    # Independence: distinct hosts, distinct organisations.
    hosts = set()
    for s in sources:
        h = urlparse(s.url).netloc.removeprefix("www.").lower() if s.url else s.name.lower()
        hosts.add(h)
    independent = len(hosts)

    stamped = [s.published_at for s in sources if s.published_at]
    earliest = min(stamped) if stamped else None

    if len(stamped) < len(sources):
        flags.append(
            f"{len(sources) - len(stamped)} of {len(sources)} sources carry no "
            "publication timestamp: original time of the claim is unestablished"
        )
    if independent == 1 and len(sources) > 1:
        flags.append(
            "multiple citations resolve to a single host: this is one source "
            "repeated, not independent confirmation"
        )
    if best_tier is Tier.SOCIAL and independent >= 3 and primary is None:
        flags.append(
            "several social accounts carrying the same claim with no primary "
            "document: the classic copy-propagation pattern"
        )
    for s in sources:
        if s.name in known_unreliable:
            flags.append(f"source '{s.name}' has a recorded history of inaccurate reporting")
    if conflicts_with_primary:
        flags.append("claim conflicts with the primary document it purports to describe")
    if market_reaction_contradicts:
        flags.append(
            "market reaction contradicts the reported information: either the claim "
            "is wrong, is already priced, or is being misread"
        )
    if claim_first_seen and earliest and earliest < claim_first_seen - timedelta(days=1):
        flags.append(
            f"earliest publication {iso(earliest)} predates first sighting by more "
            "than a day: likely recycled news resurfacing"
        )

    if primary is not None and not conflicts_with_primary:
        verification = Verification.CONFIRMED
    elif best_tier is Tier.PRIMARY:
        verification = Verification.OFFICIAL_PENDING
    elif best_tier is Tier.INSTITUTIONAL and independent >= 2:
        verification = Verification.REPORTED
    elif best_tier is Tier.INSTITUTIONAL:
        verification = Verification.REPORTED
    elif conflicts_with_primary:
        verification = Verification.DISPUTED
    else:
        verification = Verification.UNCONFIRMED

    score = credibility(
        best_tier, verification,
        independent_confirmations=max(0, independent - 1),
        has_primary_document=primary is not None,
        timestamp_clear=bool(earliest) and len(stamped) == len(sources),
        source_has_error_history=any(s.name in known_unreliable for s in sources),
    )

    if verification in (Verification.UNCONFIRMED, Verification.DISPUTED):
        actions.append("Do NOT trade this as fact. Obtain the primary document.")
    if primary is None:
        actions.append(
            f"Primary source missing. Check the issuing institution directly "
            f"before treating this as confirmed."
        )
    if independent < 2 and verification is not Verification.CONFIRMED:
        actions.append("Seek a second, genuinely independent outlet.")
    if not earliest:
        actions.append("Establish the original publication timestamp and time zone.")

    label = (
        verification.value
        if verification is not Verification.UNCONFIRMED
        else "UNCONFIRMED - REQUIRES VERIFICATION"
    )

    return ConfirmationResult(
        verification=verification, credibility_score=score, best_tier=best_tier,
        independent_sources=independent, primary_source=primary,
        earliest_publication=earliest, misinformation_flags=tuple(flags),
        required_actions=tuple(actions), label=label,
    )


__all__ = [
    "TIER1_DOMAINS", "TIER2_DOMAINS", "TIER4_DOMAINS", "ConfirmationResult",
    "classify_domain", "confirm", "make_source",
]

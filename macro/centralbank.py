"""Central-bank language intelligence (spec sections 5 and 6).

This is a lexical engine, and it says so.  It measures which policy-loaded
phrases are present, which appeared or disappeared versus a prior text, and
which were strengthened or weakened.  It does not read intent.  A tone label
from this module is an INTERPRETATION, never a FACT, and the confidence it
reports reflects how much signal-bearing language was actually found - not
how confident the sentence sounds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .types import Category, clamp


class Tone(str, Enum):
    EXTREMELY_HAWKISH = "EXTREMELY HAWKISH"
    HAWKISH = "HAWKISH"
    NEUTRAL = "NEUTRAL"
    DOVISH = "DOVISH"
    EXTREMELY_DOVISH = "EXTREMELY DOVISH"


# Weighted policy lexicon.  Positive = hawkish, negative = dovish.  Weights are
# a judgement about how much each phrase moves front-end pricing when it is the
# *new* language in a statement, and are open to recalibration.
HAWKISH: dict[str, float] = {
    r"\bfurther (?:policy )?(?:firming|tightening)\b": 3.0,
    r"\badditional (?:policy )?(?:firming|tightening)\b": 3.0,
    r"\bhigher for longer\b": 2.5,
    r"\bnot (?:yet )?(?:be )?(?:appropriate|confident) to (?:cut|ease|lower)\b": 2.5,
    r"\brestrictive (?:for|stance|policy)\b": 2.0,
    r"\bsufficiently restrictive\b": 2.0,
    r"\bunacceptably high\b": 2.5,
    r"\bmore work to do\b": 2.0,
    r"\bvigilan(?:t|ce)\b": 1.5,
    r"\binflation remains elevated\b": 1.5,
    r"\bupside risks? to inflation\b": 1.8,
    r"\bwage (?:growth|pressures) remain(?:s)? (?:strong|elevated)\b": 1.5,
    r"\bsecond[- ]round effects\b": 1.5,
    r"\bde[- ]?anchor(?:ing|ed)\b": 2.5,
    r"\btight(?:er)? labou?r market\b": 1.2,
    r"\bresilient (?:demand|economy|activity)\b": 1.0,
    r"\bprepared to (?:raise|increase) rates?\b": 3.0,
    r"\bpremature to (?:cut|ease|declare victory)\b": 2.2,
    r"\bquantitative tightening\b": 1.5,
    r"\baccelerat(?:e|ing) (?:the )?(?:runoff|balance sheet reduction)\b": 2.0,
}

DOVISH: dict[str, float] = {
    r"\brate cuts? (?:are|is) (?:appropriate|warranted|likely)\b": 3.0,
    r"\bbegin (?:to )?(?:dial(?:ing)? back|reducing) (?:policy )?restraint\b": 2.5,
    r"\bdownside risks? to (?:growth|employment|activity)\b": 2.0,
    r"\bcooling labou?r market\b": 1.8,
    r"\bsofteni?ng (?:in )?(?:demand|labou?r|activity)\b": 1.5,
    r"\bdisinflation(?:ary)?\b": 1.5,
    r"\bgained (?:greater )?confidence\b": 2.2,
    r"\bmoving (?:sustainably )?(?:toward|to) (?:the )?2 ?(?:per ?cent|%)\b": 2.0,
    r"\bwell[- ]anchored\b": 1.2,
    r"\breduce the (?:target )?range\b": 3.0,
    r"\blower(?:ing)? (?:the )?(?:policy )?rates?\b": 2.5,
    r"\bslow(?:ing)? the pace of (?:balance sheet|runoff|decline)\b": 1.8,
    r"\bease (?:the )?(?:policy )?stance\b": 2.5,
    r"\brecession(?:ary)? risks?\b": 1.8,
    r"\bfinancial (?:stability|stress) (?:risks?|concerns?)\b": 1.5,
    r"\bstand(?:s)? ready to (?:provide|supply) liquidity\b": 2.5,
    r"\baccommodat(?:ive|ion)\b": 2.0,
}

# Phrases that carry no direction but flag that guidance itself is in play.
GUIDANCE_MARKERS: dict[str, str] = {
    r"\bdata[- ]dependent\b": "explicit data dependence: guidance is being withheld",
    r"\bmeeting by meeting\b": "meeting-by-meeting: no pre-commitment, each print matters more",
    r"\bin the coming months?\b": "time-conditioned guidance",
    r"\bappropriate(?:ness)? of (?:the )?(?:policy )?(?:stance|path)\b": "stance under review",
    r"\bsome time\b": "duration guidance",
    r"\brisks? (?:are|remain) (?:broadly )?balanced\b": "risk assessment neutralised",
    r"\bdissent(?:ed|ing)?\b": "non-unanimous decision: vote split is the signal",
    r"\bunanimous(?:ly)?\b": "unanimous decision",
}

_INTENSIFIERS = ("strongly", "firmly", "clearly", "significantly", "materially",
                 "substantially", "sharply", "considerably")
_HEDGES = ("somewhat", "modestly", "gradually", "slightly", "may", "could",
           "might", "possibly", "tentatively")


@dataclass(frozen=True)
class Hit:
    phrase: str
    weight: float
    excerpt: str
    intensified: bool = False
    hedged: bool = False

    @property
    def effective(self) -> float:
        w = self.weight
        if self.intensified:
            w *= 1.35
        if self.hedged:
            w *= 0.6
        return w


@dataclass(frozen=True)
class ToneRead:
    tone: Tone
    score: float                 # signed, roughly -10..+10
    hawkish_hits: tuple[Hit, ...]
    dovish_hits: tuple[Hit, ...]
    guidance_flags: tuple[str, ...]
    signal_density: float        # matched weight per 1000 words
    confidence: float            # 0-1, driven by how much language was found
    caveats: tuple[str, ...]
    category: Category = Category.INTERPRETATION
    ok: bool = True

    def render(self) -> str:
        return (
            f"TONE {self.tone.value} (score {self.score:+.2f}, confidence "
            f"{self.confidence:.2f}) | {len(self.hawkish_hits)} hawkish / "
            f"{len(self.dovish_hits)} dovish phrases"
        )


def _scan(text: str, lex: dict[str, float]) -> list[Hit]:
    hits: list[Hit] = []
    low = text.lower()
    for pattern, weight in lex.items():
        for m in re.finditer(pattern, low):
            s, e = m.span()
            ctx = low[max(0, s - 60): min(len(low), e + 60)]
            hits.append(
                Hit(
                    phrase=m.group(0),
                    weight=weight,
                    excerpt="..." + ctx.strip() + "...",
                    intensified=any(w in ctx for w in _INTENSIFIERS),
                    hedged=any(w in ctx for w in _HEDGES),
                )
            )
    return hits


def read_tone(text: str) -> ToneRead:
    """Classify one statement, speech or press-conference transcript."""
    words = max(1, len(text.split()))
    haw = _scan(text, HAWKISH)
    dov = _scan(text, DOVISH)
    flags = [
        note for pattern, note in GUIDANCE_MARKERS.items()
        if re.search(pattern, text.lower())
    ]

    h = sum(x.effective for x in haw)
    d = sum(x.effective for x in dov)
    score = h - d
    density = 1000.0 * (h + d) / words

    if score >= 5:
        tone = Tone.EXTREMELY_HAWKISH
    elif score >= 1.5:
        tone = Tone.HAWKISH
    elif score <= -5:
        tone = Tone.EXTREMELY_DOVISH
    elif score <= -1.5:
        tone = Tone.DOVISH
    else:
        tone = Tone.NEUTRAL

    caveats = [
        "Lexical classification only: this measures policy-loaded wording, not "
        "the committee's intent, and cannot read delivery, emphasis or Q&A tone.",
    ]
    conf = clamp(20 + 12 * (len(haw) + len(dov)), 0, 85) / 100.0
    if words < 120:
        conf *= 0.6
        caveats.append(f"Short text ({words} words): a single phrase dominates the score.")
    if h > 0 and d > 0 and min(h, d) / max(h, d) > 0.6:
        conf *= 0.7
        caveats.append(
            "Two-sided language (hawkish and dovish weight are close): the text is "
            "genuinely balanced, or the committee is deliberately preserving optionality."
        )
    if not haw and not dov:
        caveats.append("No lexicon phrases matched: treat the NEUTRAL label as 'no read', not as 'neutral policy'.")

    return ToneRead(
        tone=tone,
        score=score,
        hawkish_hits=tuple(haw),
        dovish_hits=tuple(dov),
        guidance_flags=tuple(flags),
        signal_density=density,
        confidence=round(conf, 2),
        caveats=tuple(caveats),
    )


# --------------------------------------------------------------------------
# Statement diffing (spec section 5: "detect changes in language")
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class LanguageDiff:
    tone_before: Tone
    tone_after: Tone
    score_before: float
    score_after: float
    shift: float
    added_phrases: tuple[str, ...]
    removed_phrases: tuple[str, ...]
    strengthened: tuple[str, ...]
    weakened: tuple[str, ...]
    guidance_added: tuple[str, ...]
    guidance_removed: tuple[str, ...]
    sentence_changes: tuple[tuple[str, str], ...]
    headline: str
    category: Category = Category.INTERPRETATION
    ok: bool = True

    def render(self) -> str:
        return (
            f"{self.headline}\n  tone {self.tone_before.value} -> {self.tone_after.value} "
            f"(score {self.score_before:+.2f} -> {self.score_after:+.2f}, "
            f"shift {self.shift:+.2f})"
        )


def diff_statements(previous: str, current: str) -> LanguageDiff:
    """Compare two official texts and surface the wording that changed.

    Removal of a phrase is treated as a signal in its own right: central banks
    delete guidance deliberately, and the deletion usually reprices before the
    addition does.
    """
    a, b = read_tone(previous), read_tone(current)

    def keyset(r: ToneRead) -> dict[str, float]:
        out: dict[str, float] = {}
        for hit in list(r.hawkish_hits) + list(r.dovish_hits):
            out[hit.phrase] = out.get(hit.phrase, 0.0) + hit.effective
        return out

    ka, kb = keyset(a), keyset(b)
    added = tuple(sorted(set(kb) - set(ka)))
    removed = tuple(sorted(set(ka) - set(kb)))
    strengthened = tuple(sorted(p for p in set(ka) & set(kb) if kb[p] > ka[p] * 1.15))
    weakened = tuple(sorted(p for p in set(ka) & set(kb) if kb[p] < ka[p] * 0.85))

    ga, gb = set(a.guidance_flags), set(b.guidance_flags)

    sa = _sentences(previous)
    sb = _sentences(current)
    changes: list[tuple[str, str]] = []
    for s in sb:
        if s not in sa:
            near = _closest(s, sa)
            if near:
                changes.append((near, s))
    changes = changes[:8]

    shift = b.score - a.score
    if abs(shift) < 0.5:
        headline = "LANGUAGE ESSENTIALLY UNCHANGED - no material guidance shift detected"
    elif shift > 0:
        headline = f"HAWKISH LANGUAGE SHIFT (+{shift:.2f})"
    else:
        headline = f"DOVISH LANGUAGE SHIFT ({shift:.2f})"
    if removed:
        headline += f" | {len(removed)} phrase(s) DELETED from the prior text"

    return LanguageDiff(
        tone_before=a.tone, tone_after=b.tone,
        score_before=a.score, score_after=b.score, shift=shift,
        added_phrases=added, removed_phrases=removed,
        strengthened=strengthened, weakened=weakened,
        guidance_added=tuple(sorted(gb - ga)), guidance_removed=tuple(sorted(ga - gb)),
        sentence_changes=tuple(changes), headline=headline,
    )


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    return [p.strip() for p in parts if len(p.strip()) > 15]


def _closest(target: str, pool: list[str]) -> str | None:
    tt = set(target.lower().split())
    best, best_score = None, 0.0
    for cand in pool:
        ct = set(cand.lower().split())
        if not ct:
            continue
        j = len(tt & ct) / len(tt | ct)
        if j > best_score:
            best, best_score = cand, j
    return best if best_score >= 0.45 else None


# --------------------------------------------------------------------------
# Pre-speech radar (spec section 6)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SpeechRadar:
    speaker: str
    institution: str
    role: str
    voting: str
    market_prices_now: str
    hawkish_triggers: tuple[str, ...]
    dovish_triggers: tuple[str, ...]
    neutral_scenario: str
    caveats: tuple[str, ...]
    category: Category = Category.SCENARIO
    ok: bool = True


def speech_radar(
    speaker: str,
    institution: str,
    role: str,
    *,
    voting: str = "UNKNOWN",
    market_pricing_summary: str | None = None,
) -> SpeechRadar:
    """Build the pre-event trigger map for a scheduled speech.

    The triggers are generic policy-language templates, deliberately: inventing
    speaker-specific "expected remarks" would be fabrication. Supply
    ``market_pricing_summary`` from real pricing data to make it concrete.
    """
    return SpeechRadar(
        speaker=speaker,
        institution=institution,
        role=role,
        voting=voting,
        market_prices_now=market_pricing_summary
        or "UNKNOWN - supply live OIS/futures-implied probabilities; this system "
           "does not assume what is priced",
        hawkish_triggers=(
            "re-introduces optionality on further tightening ('not ruling out', "
            "'prepared to raise')",
            "calls the current stance insufficiently restrictive",
            "shifts the inflation assessment from 'easing' back to 'elevated' or "
            "'unacceptably high'",
            "flags wage growth or services inflation as inconsistent with target",
            "pushes back explicitly on the number of cuts the market has priced",
            "signals a slower balance-sheet normalisation than expected",
        ),
        dovish_triggers=(
            "states confidence that inflation is moving sustainably to target",
            "shifts emphasis from the inflation mandate to the employment mandate",
            "describes the labour market as cooling rather than merely normalising",
            "introduces a timeframe for easing ('in the coming months')",
            "acknowledges policy is already restrictive and acting with a lag",
            "raises financial-stability or funding-market concerns",
        ),
        neutral_scenario=(
            "Repeats data-dependence and meeting-by-meeting framing with no new "
            "conditionality. Front-end pricing should be roughly unchanged; any "
            "move is positioning, not information."
        ),
        caveats=(
            "Triggers are language templates, not predictions of what will be said.",
            "Voting status and blackout-window state decide whether the remarks can "
            "move pricing at all; both must be verified against the official calendar.",
            "Prepared text and Q&A can diverge sharply - the Q&A is usually where "
            "guidance actually shifts.",
        ),
    )


__all__ = [
    "DOVISH", "GUIDANCE_MARKERS", "HAWKISH", "Hit", "LanguageDiff", "SpeechRadar",
    "Tone", "ToneRead", "diff_statements", "read_tone", "speech_radar",
]

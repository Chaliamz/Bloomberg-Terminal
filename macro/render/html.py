"""Single-file HTML terminal.

Renders whatever the radar actually holds. Unknown fields render as UNKNOWN in
a muted style rather than as a plausible number, and every value carries its
source tier and timestamp. No external assets, no network calls: one file that
opens anywhere.
"""

from __future__ import annotations

import html as _html
from datetime import datetime

from ..brief import DailyBrief
from ..radar import Radar
from ..scoring import UrgencyBand
from ..state import CORE_KEYS
from ..types import Tier, iso, utcnow

CSS = """
:root{--bg:#07090c;--panel:#0d1117;--line:#1c2430;--amber:#ffb000;--green:#39d353;
--red:#ff4d4d;--blue:#58a6ff;--txt:#c9d5e1;--mute:#5b6b7d;--unknown:#7a5c1f;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);
font:12px/1.5 "SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;}
header{background:linear-gradient(90deg,#12161c,#0a0d11);border-bottom:2px solid var(--amber);
padding:10px 16px;display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px}
h1{margin:0;font-size:14px;letter-spacing:.16em;color:var(--amber);text-transform:uppercase}
.stamp{color:var(--mute);font-size:11px}
main{padding:14px;display:grid;grid-template-columns:repeat(auto-fit,minmax(430px,1fr));gap:12px}
section{background:var(--panel);border:1px solid var(--line);border-radius:3px;overflow:hidden}
section>h2{margin:0;padding:7px 11px;font-size:11px;letter-spacing:.14em;text-transform:uppercase;
color:#0a0d11;background:var(--amber);font-weight:700}
.body{padding:10px 11px;max-height:460px;overflow:auto}
table{width:100%;border-collapse:collapse}
td,th{padding:3px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--mute);font-weight:400;font-size:10px;letter-spacing:.1em;text-transform:uppercase}
.num{text-align:right;font-variant-numeric:tabular-nums}
.unknown{color:var(--unknown);font-style:italic}
.up{color:var(--green)}.down{color:var(--red)}.flat{color:var(--mute)}.amb{color:var(--blue)}
.badge{display:inline-block;padding:0 5px;border-radius:2px;font-size:10px;letter-spacing:.06em}
.t1{background:#0f3d20;color:#7ee787}.t2{background:#123047;color:#79c0ff}
.t3{background:#3d3212;color:#e3b341}.t4{background:#4a1216;color:#ff7b72}
.t9{background:#25292e;color:#8b949e}
.EXTREME{color:#fff;background:var(--red);padding:0 6px;border-radius:2px}
.HIGH{color:#0a0d11;background:var(--amber);padding:0 6px;border-radius:2px}
.MEDIUM{color:var(--amber)}.LOW{color:var(--mute)}.INFORMATIONAL{color:var(--mute)}
pre{margin:0;white-space:pre-wrap;word-break:break-word;color:var(--txt);font:inherit}
.k{color:var(--mute)}
footer{padding:12px 16px;color:var(--mute);border-top:1px solid var(--line);font-size:11px}
.warn{color:var(--amber)}
ul{margin:4px 0 4px 16px;padding:0}li{margin:2px 0}
.full{grid-column:1/-1}
"""

_TIER_CLASS = {Tier.PRIMARY: "t1", Tier.INSTITUTIONAL: "t2",
               Tier.PROFESSIONAL: "t3", Tier.SOCIAL: "t4", Tier.UNKNOWN: "t9"}


def esc(x: object) -> str:
    return _html.escape(str(x), quote=True)


def _obs_cell(obs) -> str:
    if not obs.known:
        return '<td class="num unknown">UNKNOWN</td>'
    return f'<td class="num">{esc(obs.render())}</td>'


def _tier_badge(tier: Tier) -> str:
    return f'<span class="badge {_TIER_CLASS.get(tier, "t9")}">{esc(tier.label)}</span>'


def render(radar: Radar, brief: DailyBrief | None = None, title: str = "MACRO RADAR") -> str:
    now = utcnow()
    st = radar.state
    parts: list[str] = []

    parts.append(f"<header><h1>{esc(title)}</h1>"
                 f"<div class='stamp'>generated {esc(iso(now))} &middot; regime "
                 f"{esc(st.regime.value)} &middot; core coverage {st.coverage:.0%}</div>"
                 "</header><main>")

    # --- market state ------------------------------------------------------
    rows = []
    for k in CORE_KEYS:
        o = st.get(k)
        src = o.source.name if o.source and o.source.name != "unsourced" else "-"
        badge = _tier_badge(o.source.tier) if o.source and o.source.name != "unsourced" else ""
        rows.append(
            f"<tr><td>{esc(k)}</td>{_obs_cell(o)}"
            f"<td class='k'>{esc(iso(o.as_of) or '-')}</td>"
            f"<td>{badge} {esc(src)}</td></tr>"
        )
    parts.append(_panel("Market state", (
        "<table><tr><th>field</th><th class='num'>value</th><th>as of</th>"
        "<th>source</th></tr>" + "".join(rows) + "</table>"
    )))

    # --- radar book --------------------------------------------------------
    ranked = radar.ranked()
    if ranked:
        rows = []
        for e in ranked[:25]:
            rows.append(
                f"<tr><td class='num'>{e.effective_priority:.1f}</td>"
                f"<td><span class='{e.band.value}'>{esc(e.band.value)}</span></td>"
                f"<td class='k'>{esc(iso(e.when) or 'UNKNOWN')}</td>"
                f"<td>{esc(e.title)}<br><span class='k'>{esc(e.confirmation.label)} "
                f"&middot; credibility {e.confirmation.credibility_score:.0f}</span></td></tr>"
            )
        book = ("<table><tr><th class='num'>pri</th><th>band</th><th>time</th>"
                "<th>event</th></tr>" + "".join(rows) + "</table>")
    else:
        book = ("<p class='unknown'>Event book empty. The radar reports an empty book "
                "rather than manufacturing headlines.</p>")
    parts.append(_panel("Radar &mdash; ranked by priority", book))

    # --- curve -------------------------------------------------------------
    cr = st.curve()
    if getattr(cr, "ok", False):
        items = "".join(f"<li>{esc(p)}</li>" for p in cr.pricing)  # type: ignore[union-attr]
        cav = "".join(f"<li class='warn'>{esc(c)}</li>" for c in cr.caveats)  # type: ignore[union-attr]
        curve_html = (
            f"<pre>{esc(cr.render())}</pre><ul>{items}</ul>"  # type: ignore[union-attr]
            f"<p class='k'>{esc(cr.real_yield_note)} &middot; "  # type: ignore[union-attr]
            f"{esc(cr.breakeven_note)}</p><ul>{cav}</ul>"        # type: ignore[union-attr]
        )
    else:
        curve_html = f"<p class='unknown'>{esc(cr.render())}</p>"  # type: ignore[union-attr]
    parts.append(_panel("Yield curve", curve_html))

    # --- conditions --------------------------------------------------------
    cond = st.conditions()
    if getattr(cond, "ok", False):
        contrib = "".join(
            f"<tr><td>{esc(n)}</td><td class='num {'up' if c > 0 else 'down' if c < 0 else 'flat'}'>"
            f"{c:+.2f}</td><td class='k'>{esc(w)}</td></tr>"
            for n, c, w in cond.contributions            # type: ignore[union-attr]
        )
        alarms = "".join(f"<li class='down'>{esc(a)}</li>" for a in cond.alarms)  # type: ignore[union-attr]
        cav = "".join(f"<li class='warn'>{esc(c)}</li>" for c in cond.caveats)    # type: ignore[union-attr]
        cond_html = (
            f"<pre>{esc(cond.render())}</pre>"           # type: ignore[union-attr]
            f"<table>{contrib}</table><ul>{alarms}{cav}</ul>"
            f"<p class='k'>not observed: {esc(', '.join(cond.missing))}</p>"  # type: ignore[union-attr]
        )
    else:
        cond_html = f"<p class='unknown'>{esc(cond.render())}</p>"  # type: ignore[union-attr]
    parts.append(_panel("Liquidity &amp; financial conditions", cond_html))

    # --- setups ------------------------------------------------------------
    if radar.setups:
        blocks = "".join(f"<pre>{esc(s.render())}</pre>" for s in radar.setups)
    else:
        blocks = ("<p class='unknown'>No candidate setups submitted. Setups are not "
                  "generated from nothing.</p>")
    parts.append(_panel("Setups", blocks))

    # --- brief -------------------------------------------------------------
    if brief is not None:
        secs = "".join(
            f"<h3 class='k'>{s.number}. {esc(s.title)}</h3><pre>"
            + esc("\n".join(s.lines)) + "</pre>"
            for s in brief.sections
        )
        parts.append(_panel(
            f"Daily brief &mdash; bias {esc(brief.bias)}",
            secs + f"<p class='warn'>{esc(brief.bias_reason)}</p>",
            full=True,
        ))

    parts.append("</main>")
    parts.append(
        "<footer>"
        "This terminal renders only supplied or fetched data. Fields marked "
        "<span class='unknown'>UNKNOWN</span> have no value in the system and are "
        "not estimated, back-filled or carried forward. Directional cells are "
        "INTERPRETATION derived from a stated transmission chain, not observations. "
        "Nothing here is investment advice."
        "</footer>"
    )

    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{esc(title)}</title><style>{CSS}</style></head><body>"
        + "".join(parts) + "</body></html>"
    )


def _panel(title: str, body_html: str, full: bool = False) -> str:
    cls = " class='full'" if full else ""
    return f"<section{cls}><h2>{title}</h2><div class='body'>{body_html}</div></section>"


__all__ = ["render"]

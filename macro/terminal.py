"""The live terminal: renders a Snapshot as a subscription-grade trading board.

Design contract, and the reason this file is not a template:

* Nothing on the page is a number without a source, a tier and a capture time.
* Everything that animates as "live" is genuinely computed in the browser from
  the clock: UTC time, session state, the age of each quote, and the countdown
  to the next primary release. None of it is decoration pretending to be data.
* The header states SNAPSHOT or LIVE from the actual age of the data, so the
  page can never look fresher than it is.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone

from .live import HEAT_RAMPS, Snapshot
from .reaction import ASSETS, build_matrix
from .regime import MacroRegime
from .surprise import Impulse

__all__ = ["render", "main"]


def e(x: object) -> str:
    return html.escape(str(x), quote=True)


FONTS = ("https://fonts.googleapis.com/css2?"
         "family=Chakra+Petch:wght@600;700&"
         "family=Inter:wght@400;500;600&"
         "family=JetBrains+Mono:wght@400;500;700&display=swap")

CSS = r"""
:root{
  --void:#05060A; --deep:#080A11; --panel:#0A0C14; --raise:#0F131D;
  --edge:#171C2A; --edge-hi:#232B3E;
  /* Primary accent is teal, deliberately NOT amber-on-black: that scheme is
     Bloomberg's protected brand identity. The conventions borrowed here are
     functional - density, monospace grids, hard panels, a command line. */
  --gold:#2EC5CF; --gold-dim:#155F66;
  --amber:#E8A33C; --amber-dim:#6E4E1B;
  --up:#3DDC84; --up-dim:#186340;
  --down:#FF5A6E; --down-dim:#7A2833;
  --live:#7A6CF0; --live-dim:#332C73;
  --unk:#7E76A8;
  --ink:#DCE3EE; --ink-2:#9AA6BC; --dim:#66738C; --faint:#3B455C;
  /* Validated sequential magnitude ramp: monotonic in OKLab lightness,
     step gaps 0.086-0.110, 15.9:1 contrast at the top against the ground. */
  --h0:#0D1030; --h1:#241A5E; --h2:#28407F; --h3:#22698C;
  --h4:#2A9284; --h5:#63B85C; --h6:#C8CC46; --h7:#F2E85C;
  /* JetBrains Mono carries the numbers: it has true tabular figures and a
     slashed zero, which matters more here than anything else on the page.
     Chakra Petch is the angular display face, IBM Plex Sans the reading face. */
  --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --body:"Inter",system-ui,-apple-system,"Segoe UI",sans-serif;
  --disp:"Chakra Petch","Inter",system-ui,sans-serif;
}
*{box-sizing:border-box}
html{background:var(--void)}
body{margin:0;background:var(--void);color:var(--ink);font-family:var(--body);
  font-size:15px;line-height:1.5;-webkit-font-smoothing:antialiased;overflow-x:hidden}
img{max-width:100%}
[hidden]{display:none!important}

#fx{position:fixed;inset:0;z-index:0;display:block;pointer-events:none}
.veil{position:fixed;inset:0;z-index:1;pointer-events:none;
  background:
    radial-gradient(1200px 700px at 8% -10%,rgba(46,197,207,.13),transparent 60%),
    radial-gradient(1000px 600px at 95% 0%,rgba(122,108,240,.12),transparent 58%),
    radial-gradient(1400px 900px at 50% 120%,rgba(99,184,92,.08),transparent 62%),
    radial-gradient(900px 900px at 20% 85%,rgba(232,163,60,.06),transparent 60%);
  animation:drift 34s ease-in-out infinite alternate}
@keyframes drift{
  0%{transform:translate3d(0,0,0) scale(1);filter:hue-rotate(0deg)}
  50%{transform:translate3d(-1.6%,1.2%,0) scale(1.05);filter:hue-rotate(-9deg)}
  100%{transform:translate3d(1.8%,-1%,0) scale(1.03);filter:hue-rotate(7deg)}}
/* slow chromatic wash: two counter-rotating conic sweeps, very low alpha, so it
   reads as depth rather than as a moving object competing with the data */
.aurora{position:fixed;inset:-25%;z-index:1;pointer-events:none;opacity:.30;
  background:
    conic-gradient(from 0deg at 30% 40%,rgba(46,197,207,.16),transparent 28%,
      rgba(122,108,240,.15) 52%,transparent 74%,rgba(46,197,207,.16)),
    conic-gradient(from 180deg at 72% 66%,transparent 12%,rgba(99,184,92,.12) 34%,
      transparent 58%,rgba(232,163,60,.10) 80%,transparent);
  filter:blur(74px);animation:swirl 58s linear infinite}
@keyframes swirl{to{transform:rotate(360deg)}}
/* a slow horizon sweep, the thing a live desk actually has moving on it */
.sweep{position:fixed;inset:0;z-index:2;pointer-events:none;overflow:hidden}
.sweep::before{content:"";position:absolute;top:0;bottom:0;width:36vw;left:-40vw;
  background:linear-gradient(90deg,transparent,rgba(46,197,207,.055) 42%,
    rgba(127,233,242,.085) 50%,rgba(46,197,207,.055) 58%,transparent);
  animation:sweepx 17s cubic-bezier(.5,0,.5,1) infinite}
@keyframes sweepx{0%{left:-40vw}62%,100%{left:112vw}}
/* faint drifting lattice: gives the void a sense of scale behind the panels */
.mesh{position:fixed;inset:0;z-index:1;pointer-events:none;opacity:.5;
  background-image:
    linear-gradient(rgba(46,197,207,.045) 1px,transparent 1px),
    linear-gradient(90deg,rgba(46,197,207,.045) 1px,transparent 1px);
  background-size:64px 64px;animation:mesh 42s linear infinite}
@keyframes mesh{to{background-position:64px 64px}}
.scan{position:fixed;inset:0;z-index:2;pointer-events:none;opacity:.35;
  background:repeating-linear-gradient(180deg,rgba(255,255,255,.022) 0 1px,transparent 1px 3px);
  animation:roll-scan 7.5s linear infinite}
@keyframes roll-scan{to{background-position:0 3px}}
.shell{position:relative;z-index:3}

/* ---------- masthead ---------- */
.top{position:sticky;top:0;z-index:20;border-bottom:1px solid var(--edge-hi);
  background:linear-gradient(180deg,rgba(10,12,20,.98),rgba(5,6,10,.95));
  backdrop-filter:blur(9px)}
.top-in{max-width:1720px;margin:0 auto;padding:11px 18px;display:flex;
  align-items:center;justify-content:space-between;gap:18px;flex-wrap:wrap}
.logo{display:flex;align-items:baseline;gap:12px;min-width:0}
.logo h1{margin:0;font-family:var(--disp);font-weight:700;font-size:33px;
  letter-spacing:.055em;text-transform:uppercase;color:var(--gold);line-height:1;
  text-shadow:0 0 26px rgba(46,197,207,.30)}
.logo .tier{font-family:var(--mono);font-size:10px;letter-spacing:.24em;color:var(--dim);
  text-transform:uppercase;border:1px solid var(--gold-dim);padding:2px 7px;border-radius:2px}
.hud{display:flex;gap:20px;flex-wrap:wrap;align-items:center}
.hud .cell{display:flex;flex-direction:column;gap:2px;min-width:0}
.hud .cell span{font-family:var(--mono);font-size:9.5px;letter-spacing:.2em;
  text-transform:uppercase;color:var(--faint)}
.hud .cell b{font-family:var(--mono);font-size:15.5px;font-weight:500;color:var(--ink);
  font-variant-numeric:tabular-nums;white-space:nowrap}
.pulse{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;
  background:var(--up);box-shadow:0 0 0 0 rgba(61,220,132,.7);animation:ping 2s infinite}
.pulse.stale{background:var(--amber);box-shadow:0 0 0 0 rgba(232,163,60,.7)}
.pulse.cold{background:var(--down);box-shadow:0 0 0 0 rgba(255,90,110,.7)}
@keyframes ping{0%{box-shadow:0 0 0 0 currentColor;opacity:1}
  70%{box-shadow:0 0 0 8px rgba(0,0,0,0);opacity:.75}100%{box-shadow:0 0 0 0 rgba(0,0,0,0);opacity:1}}

/* ---------- ticker ---------- */
.tape{border-bottom:1px solid var(--edge);background:rgba(8,10,17,.92);overflow:hidden;
  position:relative}
.tape::before,.tape::after{content:"";position:absolute;top:0;bottom:0;width:64px;z-index:2;
  pointer-events:none}
.tape::before{left:0;background:linear-gradient(90deg,var(--void),transparent)}
.tape::after{right:0;background:linear-gradient(270deg,var(--void),transparent)}
.tape-run{display:flex;gap:0;width:max-content;animation:roll 64s linear infinite}
.tape:hover .tape-run{animation-play-state:paused}
@keyframes roll{from{transform:translateX(0)}to{transform:translateX(-50%)}}
.tk{display:flex;align-items:baseline;gap:9px;padding:9px 22px;border-right:1px solid var(--edge);
  font-family:var(--mono);font-size:13.5px;white-space:nowrap}
.tk .s{color:var(--ink-2);letter-spacing:.12em;font-weight:500}
.tk .v{color:var(--ink);font-variant-numeric:tabular-nums}
.tk .d{font-size:12px;font-variant-numeric:tabular-nums}
.up{color:var(--up)}.down{color:var(--down)}.flat{color:var(--dim)}

/* ---------- layout ---------- */
main{max-width:1720px;margin:0 auto;padding:14px 18px 64px;
  display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:13px;align-items:start}
.card{border:1px solid var(--edge);background:var(--panel);border-radius:3px;
  display:flex;flex-direction:column;min-width:0;position:relative;overflow:hidden;
  animation:lift .55s cubic-bezier(.2,.7,.3,1) both}
.card::after{content:"";position:absolute;inset:0 0 auto 0;height:1px;
  background:linear-gradient(90deg,transparent,rgba(46,197,207,.38),transparent);
  transform:translateX(-100%);animation:sheen 9s ease-in-out infinite}
.card:nth-child(2n)::after{animation-delay:2.4s}
.card:nth-child(3n)::after{animation-delay:4.6s}
@keyframes sheen{0%,72%{transform:translateX(-100%)}86%,100%{transform:translateX(100%)}}
@keyframes lift{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.card:nth-child(1){animation-delay:.02s}.card:nth-child(2){animation-delay:.06s}
.card:nth-child(3){animation-delay:.10s}.card:nth-child(4){animation-delay:.14s}
.card:nth-child(5){animation-delay:.18s}.card:nth-child(6){animation-delay:.22s}
.card:nth-child(n+7){animation-delay:.26s}
.card>h2{margin:0;padding:9px 13px;border-bottom:1px solid var(--edge);
  background:linear-gradient(180deg,var(--raise),var(--panel));
  font-family:var(--mono);font-weight:700;font-size:11.5px;letter-spacing:.2em;
  text-transform:uppercase;color:var(--ink-2);display:flex;align-items:baseline;
  justify-content:space-between;gap:8px 12px;flex-wrap:wrap;min-width:0}
.card>h2 em{font-style:normal;color:var(--faint);font-weight:400;letter-spacing:.11em;
  flex:0 1 auto;min-width:0;text-align:right}
.bd{padding:12px 13px;display:flex;flex-direction:column;gap:11px;min-width:0}
.bd>*{min-width:0}
.bd.flush{padding:0}
.c12{grid-column:span 12}.c9{grid-column:span 9}.c8{grid-column:span 8}
.c7{grid-column:span 7}.c6{grid-column:span 6}.c5{grid-column:span 5}
.c4{grid-column:span 4}.c3{grid-column:span 3}
@media(max-width:1240px){.c9,.c8,.c7,.c6,.c5{grid-column:span 12}.c4,.c3{grid-column:span 6}}
@media(max-width:700px){.c4,.c3{grid-column:span 12}main{padding:12px 10px 48px}
  .logo h1{font-size:23px}.top-in{padding:9px 10px}.hud{gap:13px}}

/* ---------- quote grid ---------- */
/* Explicit column counts, and a twelfth (derived) cell, so every row is full at
   every breakpoint: 12 divides by 6, 4 and 2. An auto-fill grid left a dead void
   on the last row; flex-wrap stretched the two trailing cells to double width. */
.qgrid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:1px;
  background:var(--edge)}
@media(max-width:1240px){.qgrid{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(max-width:700px){.qgrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.q{min-width:0;background:var(--panel);padding:10px 12px;display:flex;
  flex-direction:column;gap:3px;position:relative;transition:background .18s ease}
/* The derived cell spans the full width: 12 quotes then tile exactly at 6, 4 and
   2 columns, and the derived strip closes the board instead of leaving a gap. */
.q.derived{grid-column:1/-1;flex-direction:row;align-items:baseline;gap:14px;
  flex-wrap:wrap;background:linear-gradient(90deg,var(--raise),var(--panel))}
.q.derived .val{color:var(--gold);font-size:24px}
.q.derived .lab{flex:none}
.q.derived .src{margin-left:auto}
.q:hover{background:var(--raise)}
.q .lab{font-family:var(--mono);font-size:10.5px;letter-spacing:.17em;text-transform:uppercase;
  color:var(--dim);display:flex;justify-content:space-between;gap:6px;align-items:center}
.q .val{font-family:var(--mono);font-size:29px;font-weight:500;color:var(--ink);
  font-variant-numeric:tabular-nums;letter-spacing:-.01em;line-height:1.1}
.q .dlt{font-family:var(--mono);font-size:13px;font-variant-numeric:tabular-nums}
.q .src{font-family:var(--mono);font-size:10px;color:var(--faint);letter-spacing:.06em;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.t{font-family:var(--mono);font-size:9.5px;letter-spacing:.1em;padding:1px 4px;border-radius:2px;
  border:1px solid;flex:none}
.t1{color:var(--up);border-color:var(--up-dim);background:rgba(61,220,132,.09)}
.t2{color:var(--amber);border-color:var(--amber-dim);background:rgba(232,163,60,.09)}
.t3{color:var(--ink-2);border-color:var(--edge-hi);background:rgba(152,163,184,.07)}
.t4{color:var(--down);border-color:var(--down-dim);background:rgba(255,90,110,.09)}
/* The confidence rail sits on the LEFT edge: on the right it reads as the next
   cell's border and the reader mis-attributes the confidence. */
.conf{position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--edge)}
.q{padding-left:15px}
.q.derived{padding-left:17px}

/* ---------- news ---------- */
.news{display:flex;flex-direction:column;max-height:520px;overflow:auto}
.nw{display:grid;grid-template-columns:44px minmax(0,1fr);gap:11px;padding:10px 13px;
  border-bottom:1px solid rgba(26,32,48,.7);transition:background .16s ease}
.nw:hover{background:var(--raise)}
.nw:last-child{border-bottom:0}
.imp{font-family:var(--mono);font-size:18px;font-weight:700;text-align:center;
  font-variant-numeric:tabular-nums;line-height:1;padding-top:2px}
.imp small{display:block;font-size:8.5px;font-weight:400;letter-spacing:.13em;
  color:var(--faint);margin-top:3px}
.nw h3{margin:0 0 5px;font-family:var(--body);font-size:15.5px;font-weight:600;
  color:var(--ink);line-height:1.35}
.nw p{margin:0 0 6px;font-size:13px;color:var(--dim);line-height:1.45}
.meta{display:flex;gap:7px;flex-wrap:wrap;align-items:center;
  font-family:var(--mono);font-size:10.5px;color:var(--faint);letter-spacing:.07em}
.meta a{color:var(--live);text-decoration:none;border-bottom:1px dotted var(--live-dim)}
.meta a:hover{color:var(--ink)}
.chip{font-family:var(--mono);font-size:10px;letter-spacing:.09em;padding:1px 5px;
  border-radius:2px;border:1px solid var(--edge-hi);color:var(--ink-2)}

/* ---------- countdown ---------- */
.rel{display:flex;flex-direction:column}
.rl{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:5px 12px;padding:9px 0;
  border-bottom:1px dashed rgba(26,32,48,.9);align-items:baseline}
.rl:last-child{border-bottom:0}
.rl .nm{font-family:var(--mono);font-size:13.5px;color:var(--ink);font-weight:500}
.rl .cd{font-family:var(--mono);font-size:19px;font-weight:700;color:var(--gold);
  font-variant-numeric:tabular-nums;white-space:nowrap;letter-spacing:.02em}
.rl .cd.hot{color:var(--down);animation:blink 1s steps(2,end) infinite}
.rl .cd.past{color:var(--faint);font-weight:400}
@keyframes blink{50%{opacity:.35}}
.rl .sub{grid-column:1/-1;font-family:var(--mono);font-size:10.5px;color:var(--faint);
  letter-spacing:.05em;overflow-wrap:anywhere}
.rl .sub a{color:var(--live-dim);text-decoration:none}
.rl .sub a:hover{color:var(--live)}

/* ---------- misc ---------- */
.kv{display:grid;grid-template-columns:minmax(0,auto) minmax(0,1fr);gap:6px 16px;
  font-family:var(--mono);font-size:13px}
.kv dt{color:var(--dim);letter-spacing:.09em;text-transform:uppercase;font-size:11px;
  padding-top:2px}
.kv dd{margin:0;color:var(--ink)}
.note{margin:0;font-size:13px;line-height:1.55;color:var(--dim);
  border-left:2px solid var(--edge-hi);padding-left:10px}
.note b{color:var(--ink-2);font-weight:600}
.warn{border-left-color:var(--amber);color:var(--ink-2)}
.bad{border-left-color:var(--down)}
.reg{font-family:var(--disp);font-size:36px;font-weight:700;letter-spacing:.05em;
  color:var(--gold);text-transform:uppercase;line-height:1;margin:0}
table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:12.5px}
th{text-align:left;font-weight:400;font-size:10px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--faint);padding:7px 13px;
  border-bottom:1px solid var(--edge);position:sticky;top:0;background:var(--panel);z-index:1}
td{padding:6px 13px;border-bottom:1px solid rgba(26,32,48,.6);color:var(--ink-2);
  vertical-align:top}
tr:last-child td{border-bottom:0}
tbody tr:hover td{background:var(--raise)}
.scroll{overflow:auto;min-width:0;max-width:100%;max-height:360px}
.scroll::-webkit-scrollbar,.news::-webkit-scrollbar{width:8px;height:8px}
.scroll::-webkit-scrollbar-thumb,.news::-webkit-scrollbar-thumb{background:var(--edge-hi);
  border-radius:4px}
.arrow{font-family:var(--mono);font-weight:700}
foot,footer{display:block;max-width:1720px;margin:0 auto;padding:18px;
  border-top:1px solid var(--edge);color:var(--dim);font-size:13px;line-height:1.6}
footer strong{color:var(--ink-2)}
footer code{font-family:var(--mono);font-size:12px;color:var(--gold)}
:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
noscript .ns{display:block;margin:14px 18px;padding:12px;border:1px solid var(--gold-dim);
  background:rgba(46,197,207,.09);color:var(--gold);font-family:var(--mono);font-size:12px}
/* ---------- sentiment gauges ---------- */
.gauges{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
@media(max-width:520px){.gauges{grid-template-columns:1fr}}
.gg{border:1px solid var(--edge);border-radius:3px;background:var(--raise);padding:12px;
  display:flex;flex-direction:column;align-items:center;gap:6px;text-align:center}
.gg svg{width:100%;height:auto;max-width:220px;display:block}
.gg .gv{font-family:var(--mono);font-size:34px;font-weight:700;line-height:1;
  font-variant-numeric:tabular-nums}
.gg .gb{font-family:var(--disp);font-size:16px;font-weight:700;letter-spacing:.14em;
  text-transform:uppercase}
.gg .gl{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--dim)}
.gg .gs{font-family:var(--mono);font-size:10px;color:var(--faint)}
.needle{transform-origin:center;animation:swing 1.1s cubic-bezier(.3,1.4,.4,1) both .3s}
@keyframes swing{from{opacity:0}to{opacity:1}}

/* ---------- liquidation map ---------- */
.liqbar{display:flex;height:30px;border:1px solid var(--edge);border-radius:3px;
  overflow:hidden;font-family:var(--mono);font-size:12px;font-weight:700}
.liqbar span{display:flex;align-items:center;justify-content:center;color:#05060A;
  white-space:nowrap;overflow:hidden;transition:flex-basis .6s ease}
.liqbar .ls{background:var(--up)}
.liqbar .ll{background:var(--down)}
.ladder{display:flex;flex-direction:column;gap:0;font-family:var(--mono);font-size:12.5px}
.lr{display:grid;grid-template-columns:52px minmax(0,1fr) 52px;gap:8px;align-items:center;
  padding:5px 0;border-bottom:1px solid rgba(26,32,48,.6)}
.lr:last-child{border-bottom:0}
.lr .lev{color:var(--gold);font-weight:700;text-align:right}
.lr .rng{position:relative;height:22px;border-left:1px solid var(--edge);
  border-right:1px solid var(--edge)}
.lr .seg{position:absolute;top:6px;height:10px;border-radius:2px}
.lr .seg.dn{background:linear-gradient(90deg,rgba(255,90,110,.78),rgba(255,90,110,.12))}
.lr .seg.upl{background:linear-gradient(90deg,rgba(61,220,132,.12),rgba(61,220,132,.78))}
.lr .mid{position:absolute;top:0;bottom:0;width:2px;background:var(--gold);left:50%;
  transform:translateX(-50%)}
.lr .px{font-variant-numeric:tabular-nums;font-size:11.5px}
.lr .px.dn{color:var(--down);text-align:right}
.lr .px.up{color:var(--up)}
.spotline{display:flex;justify-content:space-between;font-family:var(--mono);font-size:11px;
  color:var(--faint);letter-spacing:.1em;text-transform:uppercase}

/* ---------- geopolitical board ---------- */
.geo{display:flex;flex-direction:column}
.ge{display:grid;grid-template-columns:56px minmax(0,1fr);gap:12px;padding:11px 0;
  border-bottom:1px solid rgba(26,32,48,.7)}
.ge:last-child{border-bottom:0}
.sev{font-family:var(--mono);font-size:19px;font-weight:700;text-align:center;line-height:1;
  font-variant-numeric:tabular-nums}
.sev small{display:block;font-size:8.5px;font-weight:400;letter-spacing:.12em;
  color:var(--faint);margin-top:4px}
.ge h4{margin:0 0 4px;font-size:14.5px;font-weight:600;color:var(--ink);line-height:1.35}
.ge .ch{margin:0 0 6px;font-size:12.5px;color:var(--dim);line-height:1.5;
  border-left:2px solid var(--down-dim);padding-left:9px}
.stat{font-family:var(--mono);font-size:9.5px;letter-spacing:.13em;padding:2px 6px;
  border-radius:2px;border:1px solid;text-transform:uppercase}
.stat.esc{color:var(--down);border-color:var(--down-dim);background:rgba(255,90,110,.11);
  animation:blink 1.8s steps(2,end) infinite}
.stat.act{color:var(--amber);border-color:var(--amber-dim);background:rgba(232,163,60,.1)}
.stat.ong{color:var(--ink-2);border-color:var(--edge-hi)}

/* ---------- flows ---------- */
.flows{display:flex;flex-direction:column}
.fl{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 14px;padding:9px 0;
  border-bottom:1px solid rgba(26,32,48,.7);align-items:baseline}
.fl:last-child{border-bottom:0}
.fl .fn{font-family:var(--mono);font-size:13px;color:var(--ink)}
.fl .fv{font-family:var(--mono);font-size:17px;font-weight:700;font-variant-numeric:tabular-nums}
.fl .fv.in{color:var(--up)}.fl .fv.out{color:var(--down)}
.fl .fw{grid-column:1/-1;font-family:var(--mono);font-size:10.5px;color:var(--faint)}

/* ---------- squawk ---------- */
.sq{display:flex;flex-direction:column;max-height:600px;overflow:auto}
.sqr{display:grid;grid-template-columns:62px 4px minmax(0,1fr);gap:0 11px;padding:9px 13px;
  border-bottom:1px solid rgba(26,32,48,.7);transition:background .16s ease}
.sqr:hover{background:var(--raise)}
.sqr:last-child{border-bottom:0}
.sqt{font-family:var(--mono);font-size:11.5px;color:var(--dim);
  font-variant-numeric:tabular-nums;padding-top:2px}
.sqrail{border-radius:2px}
.sqb h3{margin:0 0 4px;font-size:14.5px;font-weight:600;color:var(--ink);line-height:1.35}
.sqb p{margin:0 0 5px;font-size:12.5px;color:var(--dim);line-height:1.45}

/* ---------- terminal chrome: command line + function strip ---------- */
.cmdbar{display:flex;align-items:stretch;gap:0;border-bottom:1px solid var(--edge);
  background:var(--deep);overflow-x:auto}
.cmdbar .fk{flex:0 0 auto;padding:7px 13px;border-right:1px solid var(--edge);
  font-family:var(--mono);font-size:11.5px;letter-spacing:.09em;color:var(--dim);
  white-space:nowrap;display:flex;align-items:center;gap:7px;
  transition:color .15s ease,background .15s ease}
.cmdbar .fk:hover{color:var(--ink);background:var(--raise)}
.cmdbar .fk b{color:var(--gold);font-weight:700}
.cmdbar .prompt{flex:1 1 auto;display:flex;align-items:center;gap:9px;padding:7px 14px;
  font-family:var(--mono);font-size:12px;color:var(--faint);min-width:150px}
.cmdbar .prompt .caret{width:8px;height:15px;background:var(--gold);
  animation:caret 1.1s steps(2,end) infinite}
@keyframes caret{50%{opacity:0}}
.statusbar{display:flex;flex-wrap:wrap;gap:0;border-top:1px solid var(--edge);
  background:var(--deep);font-family:var(--mono);font-size:11px;color:var(--dim)}
.statusbar span{padding:6px 14px;border-right:1px solid var(--edge);white-space:nowrap}
.statusbar b{color:var(--ink-2);font-weight:500}

/* ---------- liquidation heatmap ---------- */
.hm-ctl{display:flex;flex-wrap:wrap;gap:7px 18px;align-items:center;
  padding:9px 11px;border:1px solid var(--edge);border-radius:3px;
  background:var(--raise);font-family:var(--mono);font-size:10.5px}
.ctl-g{display:flex;align-items:center;gap:5px;flex-wrap:wrap}
.ctl-g>b{color:var(--faint);letter-spacing:.18em;font-weight:400;margin-right:2px}
.ctl-v{font-style:normal;color:var(--gold);min-width:34px;text-align:right;
  font-variant-numeric:tabular-nums}
.ctl-x{font-style:normal;color:var(--faint);padding:0 2px}
input[type=number]{width:52px;background:var(--panel);border:1px solid var(--edge-hi);
  color:var(--ink);font-family:var(--mono);font-size:10.5px;padding:2px 4px;
  border-radius:2px}
.hm-hint{margin:0;font-family:var(--mono);font-size:10px;color:var(--faint);
  letter-spacing:.06em}
.pill{font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;padding:3px 9px;
  border-radius:2px;border:1px solid var(--edge-hi);background:var(--panel);
  color:var(--dim);cursor:pointer;transition:all .14s ease}
.pill:hover{color:var(--ink);border-color:var(--gold-dim)}
.pill[data-on]{background:var(--gold);border-color:var(--gold);color:#05060A;
  font-weight:700}
.sw-btn{padding:2px;border:1px solid var(--edge-hi);background:var(--panel);
  border-radius:2px;cursor:pointer;line-height:0}
.sw-btn i{display:block;width:34px;height:12px;border-radius:1px}
.sw-btn[data-on]{border-color:var(--gold);box-shadow:0 0 0 1px var(--gold)}
input[type=range]{width:104px;accent-color:var(--gold);cursor:pointer}

.hm-stage{display:grid;grid-template-columns:42px minmax(0,1fr) 70px;
  grid-template-rows:auto auto;gap:0 8px;font-family:var(--mono);font-size:10.5px}
.hm-scale{grid-row:1;display:flex;flex-direction:column;align-items:stretch;gap:4px;
  color:var(--faint);text-align:right;font-size:9.5px}
.hm-scale i{font-style:normal;white-space:nowrap}
.hm-bar{flex:1 1 auto;border:1px solid var(--edge);border-radius:2px;min-height:60px}
.hm{grid-row:1;border:1px solid var(--edge);background:#440154;width:100%;
  display:block;aspect-ratio:1152/832}
.hm-price{grid-row:1;display:flex;flex-direction:column;justify-content:space-between;
  color:var(--faint);padding:1px 0;font-size:10px;text-align:left}
.hm-time{grid-column:2;grid-row:2;display:flex;justify-content:space-between;
  color:var(--faint);padding-top:5px;font-size:10px;overflow:hidden}
.hm-time span{white-space:nowrap}
.hm-key{display:flex;gap:14px;flex-wrap:wrap;color:var(--faint);
  font-family:var(--mono);font-size:10.5px;padding-top:2px}
.hm-key i{font-style:normal;display:inline-flex;align-items:center;gap:5px}
.hm-field{grid-row:1;position:relative;min-width:0}
.hm-field .hm{width:100%}
.hm-hair{position:absolute;left:0;top:0;width:0;height:0;pointer-events:none;z-index:3}
.hm-hair::before,.hm-hair::after{content:"";position:absolute;background:rgba(234,246,255,.42)}
.hm-hair::before{left:0;top:-4000px;width:1px;height:8000px}
.hm-hair::after{top:0;left:-4000px;height:1px;width:8000px}
.hm-tip{position:absolute;z-index:4;pointer-events:none;transform:translate(14px,-50%);
  background:rgba(6,8,14,.94);border:1px solid var(--edge-hi);border-radius:3px;
  padding:7px 10px;font-family:var(--mono);font-size:11px;line-height:1.5;
  display:grid;grid-template-columns:auto auto;gap:1px 10px;white-space:nowrap;
  box-shadow:0 8px 26px rgba(0,0,0,.6)}
.hm-tip[data-flip="1"]{transform:translate(-100%,-50%) translateX(-14px)}
.hm-tip b{color:var(--ink);font-variant-numeric:tabular-nums;font-weight:600}
.hm-tip i{font-style:normal;color:var(--dim);letter-spacing:.08em}
.hm-tip u{grid-column:1/-1;text-decoration:none;color:var(--faint);font-size:10px;
  border-top:1px solid var(--edge);padding-top:3px;margin-top:2px}
.hm-price{cursor:ns-resize;transition:color .15s ease}
.hm-price:hover{color:var(--gold)}
.hm-ctl .pill[data-off]{opacity:.3;cursor:not-allowed;text-decoration:line-through}
.hm-key .sw{width:16px;height:3px;border-radius:2px;display:inline-block}

/* ---------- stocks & earnings ---------- */
.eq{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;
  background:var(--edge)}
.eqc{background:var(--panel);padding:9px 11px;display:flex;flex-direction:column;gap:2px}
.eqc .eqt{font-family:var(--mono);font-size:14px;font-weight:700;color:var(--ink);
  letter-spacing:.06em}
.eqc .nm2{font-size:11px;color:var(--dim)}
.eqc .cap{font-family:var(--mono);font-size:18px;color:var(--gold);
  font-variant-numeric:tabular-nums;line-height:1.15}
.eqc .mv{font-family:var(--mono);font-size:12.5px;font-variant-numeric:tabular-nums}
.eqc .sr{font-family:var(--mono);font-size:9.5px;color:var(--faint);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.earn{display:flex;flex-direction:column}
.er{display:grid;grid-template-columns:64px minmax(0,1fr) auto;gap:4px 12px;
  padding:10px 0;border-bottom:1px dashed rgba(23,28,42,.9);align-items:baseline}
.er:last-child{border-bottom:0}
.er .etk{font-family:var(--mono);font-size:14px;font-weight:700;color:var(--ink)}
.er .enm{font-size:13px;color:var(--ink-2)}
.er .ecd{font-family:var(--mono);font-size:17px;font-weight:700;color:var(--gold);
  font-variant-numeric:tabular-nums;white-space:nowrap}
.er .ecd.soon{color:var(--down);animation:blink 1.2s steps(2,end) infinite}
.er .ecd.done{color:var(--faint);font-weight:400}
.er .ecd.win{color:var(--amber);font-size:12px;font-weight:500}
.er .esub{grid-column:1/-1;font-family:var(--mono);font-size:10px;color:var(--faint);
  overflow-wrap:anywhere}
.er .esub a{color:var(--live-dim);text-decoration:none}
.er .esub a:hover{color:var(--live)}
.ses{font-family:var(--mono);font-size:9px;letter-spacing:.1em;padding:1px 5px;
  border-radius:2px;border:1px solid var(--edge-hi);color:var(--ink-2)}

/* ---------- geo time badge ---------- */
.when{display:flex;flex-direction:column;align-items:flex-end;gap:2px;flex:none;
  font-family:var(--mono);text-align:right}
.when .abs{font-size:11px;color:var(--ink-2);white-space:nowrap}
.when .ago{font-size:10px;color:var(--gold);letter-spacing:.08em}
.ge{grid-template-columns:56px minmax(0,1fr) auto}
.ge .hd{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}

@media(prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:.001ms!important;
    animation-iteration-count:1!important;transition-duration:.001ms!important}
  .tape-run{animation:none}
}
"""

JS = r"""
(function(){
"use strict";
var D=window.__TERM__;
function q(id){return document.getElementById(id);}
function setText(id,v){var el=q(id);if(el){el.textContent=v;}}
function pad(n){return (n<10?"0":"")+n;}

/* ---- UTC clock + session state (computed, not decorative) ---- */
var SESSIONS=[
  {n:"TOKYO", o:0,   c:6},
  {n:"LONDON",o:7,   c:16},
  {n:"NEW YORK",o:13.5,c:20}
];
function sessionState(d){
  var h=d.getUTCHours()+d.getUTCMinutes()/60, day=d.getUTCDay(), open=[];
  if(day>=1&&day<=5){
    for(var i=0;i<SESSIONS.length;i++){
      var s=SESSIONS[i];
      if(h>=s.o&&h<s.c) open.push(s.n);
    }
  }
  return open.length?open.join(" + "):"CLOSED";
}
function tick(){
  var d=new Date();
  setText("clk",pad(d.getUTCHours())+":"+pad(d.getUTCMinutes())+":"+pad(d.getUTCSeconds())+" UTC");
  setText("sess",sessionState(d));
  setText("sb-clk",pad(d.getUTCHours())+":"+pad(d.getUTCMinutes())+":"+pad(d.getUTCSeconds()));
  /* Age ticks upward from the newest OBSERVATION, not from the capture time:
     re-running a scan that fetched nothing must not reset this to zero. */
  var cap=Date.parse(D.newest||D.captured);
  if(!isNaN(cap)){
    var s=Math.max(0,Math.floor((d.getTime()-cap)/1000));
    var dd=Math.floor(s/86400), hh=Math.floor(s%86400/3600), mm=Math.floor(s%3600/60);
    var ageTxt=(dd?dd+"d ":"")+pad(hh)+"h "+pad(mm)+"m";
    setText("age",ageTxt); setText("sb-age",ageTxt);
    var dot=q("dot"), st=q("state");
    var cls=s<900?"":(s<86400?"stale":"cold");
    var lab=s<900?"LIVE":(s<86400?"SNAPSHOT":"STALE SNAPSHOT");
    if(dot) dot.className="pulse "+cls;
    if(st){st.textContent=lab;
      st.style.color=(cls===""?"var(--up)":(cls==="stale"?"var(--gold)":"var(--down)"));}
  }
  /* day-granularity countdowns: date published, hour not */
  var dayEls=document.querySelectorAll("[data-days]");
  for(var k=0;k<dayEls.length;k++){
    var dt=Date.parse(dayEls[k].getAttribute("data-days"));
    if(isNaN(dt)){dayEls[k].textContent="UNKNOWN";continue;}
    var ds=Math.floor((dt-d.getTime())/86400000);
    if(dt-d.getTime()<=0){dayEls[k].textContent="DUE";dayEls[k].className="ecd soon";}
    else{
      dayEls[k].textContent=ds+"d";
      dayEls[k].className="ecd"+(ds<=2?" soon":"");
    }
  }
  /* release countdowns */
  var rows=document.querySelectorAll("[data-when]");
  for(var j=0;j<rows.length;j++){
    var el=rows[j], t=Date.parse(el.getAttribute("data-when"));
    if(isNaN(t)) continue;
    var diff=Math.floor((t-d.getTime())/1000);
    if(diff<=0){el.textContent="RELEASED";el.className="cd past";continue;}
    var D2=Math.floor(diff/86400),H=Math.floor(diff%86400/3600),
        M=Math.floor(diff%3600/60),S=diff%60;
    el.textContent=(D2?D2+"d ":"")+pad(H)+":"+pad(M)+":"+pad(S);
    el.className="cd"+(diff<3600?" hot":"");
  }
}
tick();setInterval(tick,1000);


/* ---- liquidation heatmap engine: a direct port of macro/live.py.
   tests/test_live.py runs this in node against the Python implementation and
   fails if the two grids diverge, so the controls below cannot drift from the
   reference model. ---- */
function heatmapCompute(anchors, opts){
  opts = opts || {};
  var levels = opts.levels;
  /* omitted -> full spectrum; explicitly empty -> refuse. Must match live.py. */
  if(levels == null){ levels = []; for(var L=2;L<=125;L++) levels.push(L); }
  if(!levels.length) return {ok:false, reason:"no leverage tiers in the model"};
  var columns = opts.columns || 36, rows = opts.rows || 34;
  var pts = anchors.slice().sort(function(a,b){return a.date < b.date ? -1 : 1;});
  if(pts.length < 2 || columns < 2 || rows < 2)
    return {ok:false, reason:"need at least two dated price anchors"};
  var prices = pts.map(function(a){return a.price;});
  var lo = opts.lo != null ? opts.lo : Math.min.apply(null, prices)*0.97;
  var hi = opts.hi != null ? opts.hi : Math.max.apply(null, prices)*1.03;
  if(hi <= lo) return {ok:false, reason:"degenerate price range"};
  var t0 = Date.parse(pts[0].date), t1 = Date.parse(pts[pts.length-1].date);
  var span = (t1 - t0)/1000;
  if(!(span > 0)) return {ok:false, reason:"all anchors share one timestamp"};

  function colOf(iso){
    var f = ((Date.parse(iso)-t0)/1000)/span;
    return Math.max(0, Math.min(columns-1, Math.floor(f*(columns-1)+0.5)));
  }
  function rowOf(p){
    var f = (p-lo)/(hi-lo);
    return Math.max(0, Math.min(rows-1, Math.floor(f*rows)));
  }
  var grid = [], x, y;
  for(x=0;x<columns;x++){ grid.push(new Array(rows).fill(0)); }
  var pending = [], lastPrice = pts[0].price, anchorAt = {};
  pts.forEach(function(a){ anchorAt[colOf(a.date)] = a; });

  for(var c=0;c<columns;c++){
    var a = anchorAt[c];
    if(a){
      var sLo = Math.min(lastPrice,a.price), sHi = Math.max(lastPrice,a.price);
      pending = pending.filter(function(p){ return !(sLo <= p[0] && p[0] <= sHi); });
      levels.forEach(function(n){
        pending.push([a.price*(1-1/n), n, "long"]);
        pending.push([a.price*(1+1/n), n, "short"]);
      });
      lastPrice = a.price;
    }
    for(var k=0;k<pending.length;k++){
      var lv = pending[k][0];
      /* uniform weight per (anchor, tier, side) - see macro/live.py */
      if(lv >= lo && lv <= hi) grid[c][rowOf(lv)] += 1.0;
    }
  }
  var peak = 0;
  for(x=0;x<columns;x++) for(y=0;y<rows;y++) if(grid[x][y]>peak) peak=grid[x][y];
  if(!(peak > 0)) return {ok:false, reason:"no pending levels fell inside the price range"};
  var norm = grid.map(function(col){
    /* floor(x+0.5), not Math.round: must match macro/live.py exactly */
    return col.map(function(v){ return Math.floor(v/peak*1e4+0.5)/1e4; });
  });
  return {ok:true, columns:columns, rows:rows, lo:lo, hi:hi, grid:norm, peak:peak,
          levels:levels, t0:pts[0].date, t1:pts[pts.length-1].date,
          anchors: pts.map(function(a){
            return {col:colOf(a.date), row:rowOf(a.price), price:a.price,
                    date:a.date, source:a.source, tier:a.tier};
          })};
}

/* ---- heatmap controller: every control recomputes the model ---- */
(function(){
  var cv=q("hm-canvas"); if(!cv||!cv.getContext||!D.anchors||D.anchors.length<2) return;
  var g=cv.getContext("2d"); if(!g) return;
  var BASE={lo:D.window&&D.window.lo, hi:D.window&&D.window.hi};
  function tiers(a,b){var o=[];for(var i=a;i<=b;i++)o.push(i);return o;}
  var ST={days:0, lmin:2, lmax:125, cols:160, rows:90,
          scheme:"viridis", thr:0, zoom:1, pan:0, chart:"candle"};
  /* screen positions of the drawn observations, rebuilt on every draw and read
     by the crosshair. Declared here so a crosshair move before the first draw
     finds an empty array rather than throwing. */
  var LAST=[];
  /* the band currently painted, so the crosshair reports the price under the
     cursor rather than the un-zoomed sourced band. */
  var CUR={lo:0, hi:1};

  function hex(h){return [parseInt(h.substr(1,2),16),parseInt(h.substr(3,2),16),
                          parseInt(h.substr(5,2),16)];}
  function ramp(){ return (D.ramps[ST.scheme]||D.ramps.viridis).map(hex); }
  function colour(v,st){
    if(v<=ST.thr) return st[0];
    var t=(v-ST.thr)/(1-ST.thr||1);
    var f=Math.min(1,Math.max(0,Math.pow(t,0.55)))*(st.length-1);
    var i=Math.floor(f), k=f-i, A=st[i], B=st[Math.min(i+1,st.length-1)];
    return [A[0]+(B[0]-A[0])*k, A[1]+(B[1]-A[1])*k, A[2]+(B[2]-A[2])*k];
  }
  function windowed(){
    var all=D.anchors;
    if(!ST.days) return all;
    var last=Date.parse(all[all.length-1].date);
    var cut=last-ST.days*86400000;
    return all.filter(function(a){return Date.parse(a.date)>=cut;});
  }
  function bounds(){
    if(BASE.lo==null||BASE.hi==null) return {};
    var mid=(BASE.lo+BASE.hi)/2 + ST.pan*(BASE.hi-BASE.lo);
    var half=(BASE.hi-BASE.lo)/2/ST.zoom;   /* zoom < 1 widens the window */
    return {lo:mid-half, hi:mid+half};
  }
  function fmt(n){
    return n>=1000 ? n.toLocaleString("en-US",{maximumFractionDigits:0})
                   : n.toFixed(2);
  }
  function draw(){
    var pts=windowed();
    var meta=q("hm-meta"), price=q("hm-price"), time=q("hm-time");
    if(pts.length<2){
      g.fillStyle="#0A0C14"; g.fillRect(0,0,cv.width,cv.height);
      g.fillStyle="#66738C"; g.font="20px monospace"; g.textAlign="center";
      g.fillText("only "+pts.length+" sourced anchor in this window",
                 cv.width/2, cv.height/2);
      g.textAlign="left";
      LAST=[];
      if(meta) meta.textContent="window too short for the data held";
      if(price) price.innerHTML=""; if(time) time.innerHTML="";
      return;
    }
    var bb=bounds();
    var H=heatmapCompute(pts,{levels:tiers(ST.lmin,ST.lmax), columns:ST.cols,
                              rows:ST.rows, lo:bb.lo, hi:bb.hi});
    if(!H.ok){
      g.fillStyle="#0A0C14"; g.fillRect(0,0,cv.width,cv.height);
      g.fillStyle="#66738C"; g.font="18px monospace"; g.textAlign="center";
      g.fillText(H.reason, cv.width/2, cv.height/2); g.textAlign="left";
      LAST=[];
      if(meta) meta.textContent=H.reason;
      return;
    }
    CUR={lo:H.lo, hi:H.hi};
    var st=ramp(), CW=cv.width/H.columns, CH=cv.height/H.rows, x, y;
    for(x=0;x<H.columns;x++){
      for(y=0;y<H.rows;y++){
        var c=colour(H.grid[x][y],st);
        g.fillStyle="rgb("+(c[0]|0)+","+(c[1]|0)+","+(c[2]|0)+")";
        g.fillRect(Math.floor(x*CW),Math.floor((H.rows-1-y)*CH),
                   Math.ceil(CW),Math.ceil(CH));
      }
    }
    /* ---- price series -------------------------------------------------
       Positions are computed from the real timestamp and price, NOT from the
       quantised grid cell the old overlay used: at COARSE resolution a cell is
       five hours wide and the track visibly sat in the wrong place.

       Candle bodies span observation to observation - open is the previous
       observation, close is this one. That is exactly what is known. The
       intrabar high and low were never observed, so the wick is drawn only to
       the body extremes and never beyond: no invented range. Where a real
       intraday range exists (4 September carries two prints) the body shows it.

       Up is near-white and down is hot red rather than the usual green/red:
       green disappears into the middle of every sequential ramp on the field
       behind it, and a series you cannot see is not a series. */
    var t0m=Date.parse(H.t0), t1m=Date.parse(H.t1), tspan=t1m-t0m;
    function px(iso){ return tspan>0 ? (Date.parse(iso)-t0m)/tspan*cv.width : cv.width/2; }
    function py(v){ return (1-(v-H.lo)/(H.hi-H.lo))*cv.height; }
    LAST=H.anchors.map(function(a){
      return {x:px(a.date), y:py(a.price), price:a.price, date:a.date,
              source:a.source, tier:a.tier};
    });
    var gaps=[], i;
    for(i=1;i<LAST.length;i++) gaps.push(LAST[i].x-LAST[i-1].x);
    gaps.sort(function(a,b){return a-b;});
    /* MEDIAN, not minimum: 4 September carries two prints 3h21m apart, and
       sizing every candle to that one pair collapsed the series to hairlines. */
    var gap=gaps.length?gaps[Math.floor(gaps.length/2)]:cv.width/12;
    var bw=Math.max(3, Math.min(34, gap*0.68));

    g.save(); g.lineJoin="round"; g.lineCap="butt";
    if(ST.chart!=="off"){
      if(ST.chart==="line"||ST.chart==="area"){
        if(ST.chart==="area"){
          var grd=g.createLinearGradient(0,0,0,cv.height);
          grd.addColorStop(0,"rgba(46,197,207,.40)");
          grd.addColorStop(1,"rgba(46,197,207,0)");
          g.beginPath(); g.moveTo(LAST[0].x,cv.height);
          LAST.forEach(function(p){g.lineTo(p.x,p.y);});
          g.lineTo(LAST[LAST.length-1].x,cv.height); g.closePath();
          g.fillStyle=grd; g.fill();
        }
        g.strokeStyle="rgba(5,6,10,.85)"; g.lineWidth=4.6;
        g.beginPath(); LAST.forEach(function(p,k){k?g.lineTo(p.x,p.y):g.moveTo(p.x,p.y);});
        g.stroke();
        g.strokeStyle="#7FE9F2"; g.lineWidth=1.9;
        g.beginPath(); LAST.forEach(function(p,k){k?g.lineTo(p.x,p.y):g.moveTo(p.x,p.y);});
        g.stroke();
      } else {
        for(i=1;i<LAST.length;i++){
          var a=LAST[i-1], b=LAST[i], up=b.price>=a.price;
          var top=Math.min(a.y,b.y), bot=Math.max(a.y,b.y);
          var cx=b.x, h=Math.max(1.5,bot-top);
          g.strokeStyle="rgba(4,5,9,.92)";
          if(ST.chart==="bar"){
            g.lineWidth=Math.max(3.4,bw*0.30);
            g.beginPath(); g.moveTo(cx,top); g.lineTo(cx,bot); g.stroke();
            g.beginPath(); g.moveTo(cx-bw*0.5,a.y); g.lineTo(cx,a.y);
            g.moveTo(cx,b.y); g.lineTo(cx+bw*0.5,b.y); g.stroke();
            g.strokeStyle=up?"#EAF6FF":"#FF4D6D";
            g.lineWidth=Math.max(1.6,bw*0.16);
            g.beginPath(); g.moveTo(cx,top); g.lineTo(cx,bot); g.stroke();
            g.beginPath(); g.moveTo(cx-bw*0.5,a.y); g.lineTo(cx,a.y);
            g.moveTo(cx,b.y); g.lineTo(cx+bw*0.5,b.y); g.stroke();
          } else {
            g.lineWidth=Math.max(2.6,bw*0.22);
            g.beginPath(); g.moveTo(cx,top); g.lineTo(cx,bot); g.stroke();
            g.strokeStyle=up?"#EAF6FF":"#FF4D6D";
            g.lineWidth=Math.max(1.2,bw*0.11);
            g.beginPath(); g.moveTo(cx,top); g.lineTo(cx,bot); g.stroke();
            g.fillStyle=up?"#EAF6FF":"#FF4D6D";
            g.strokeStyle="rgba(4,5,9,.92)"; g.lineWidth=1.4;
            g.beginPath(); g.rect(cx-bw/2,top,bw,h); g.fill(); g.stroke();
          }
        }
        /* the first observation has no predecessor, so it is a mark, not a bar */
        var f=LAST[0];
        g.strokeStyle="rgba(4,5,9,.92)"; g.lineWidth=4.2;
        g.beginPath(); g.moveTo(f.x-bw*0.5,f.y); g.lineTo(f.x+bw*0.5,f.y); g.stroke();
        g.strokeStyle="#9FB2C9"; g.lineWidth=2;
        g.beginPath(); g.moveTo(f.x-bw*0.5,f.y); g.lineTo(f.x+bw*0.5,f.y); g.stroke();
      }
      /* the latest observation, marked the way a chart marks last price */
      var L=LAST[LAST.length-1];
      g.setLineDash([5,5]); g.strokeStyle="rgba(127,233,242,.55)"; g.lineWidth=1;
      g.beginPath(); g.moveTo(0,L.y); g.lineTo(cv.width,L.y); g.stroke();
      g.setLineDash([]);
    }
    g.restore();

    if(price){
      var out="";
      for(var i=6;i>=0;i--) out+="<span>"+fmt(H.lo+(H.hi-H.lo)*i/6)+"</span>";
      price.innerHTML=out;
    }
    if(time){
      var t0=H.t0.slice(5,10), t1=H.t1.slice(5,10);
      var m0=Date.parse(H.t0), m1=Date.parse(H.t1), tout="";
      for(var j=0;j<5;j++){
        var d2=new Date(m0+(m1-m0)*j/4);
        tout+="<span>"+String(d2.getUTCMonth()+1).padStart(2,"0")+"-"+
              String(d2.getUTCDate()).padStart(2,"0")+"</span>";
      }
      time.innerHTML=tout;
    }
    var bar=q("hm-bar");
    if(bar) bar.style.background="linear-gradient(0deg,"+
      (D.ramps[ST.scheme]||D.ramps.viridis).join(",")+")";
    setText("hm-peak",H.peak.toFixed(1));
    if(meta) meta.textContent=pts.length+" sourced anchors · "+
      H.columns+"×"+H.rows+" grid · "+(ST.lmax-ST.lmin+1)+" leverage tiers "+
      ST.lmin+"x-"+ST.lmax+"x · "+fmt(H.lo)+"-"+fmt(H.hi)+
      " · zoom "+ST.zoom.toFixed(2)+"x";
    setText("hm-zv",ST.zoom.toFixed(2)+"×");
  }

  function bindPills(sel, fn){
    document.querySelectorAll(sel).forEach(function(b){
      b.addEventListener("click",function(){ fn(b); draw(); });
    });
  }
  /* Not every window the bar offers is a view the data can support. A window
     holding fewer than two sourced anchors cannot produce a heatmap at all, and
     one holding the same anchors as a narrower window renders identically - both
     would be buttons that do nothing. Gate them, and say why on hover, rather
     than shipping dead controls. Anchor sets are nested as the window widens, so
     an equal count means an equal set. */
  function anchorsIn(days){
    if(!days) return D.anchors.length;
    var last=Date.parse(D.anchors[D.anchors.length-1].date);
    var cut=last-days*86400000;
    return D.anchors.filter(function(a){return Date.parse(a.date)>=cut;}).length;
  }
  (function gateWindows(){
    var seen={}, btns=[].slice.call(document.querySelectorAll("[data-tf]"));
    btns.sort(function(a,b){
      var x=parseInt(a.getAttribute("data-tf"),10)||1e9;
      var y=parseInt(b.getAttribute("data-tf"),10)||1e9;
      return x-y;
    });
    btns.forEach(function(b){
      var d=parseInt(b.getAttribute("data-tf"),10);
      var n=anchorsIn(d), why=null;
      if(n<2) why=n+" sourced anchor in this window \u2014 a heatmap needs two";
      else if(seen[n]) why="same anchors as "+seen[n]+" \u2014 no observation between them";
      else seen[n]=(d?d+"D":"ALL");
      if(why){
        b.disabled=true; b.setAttribute("data-off","1");
        b.removeAttribute("data-on"); b.title=why;
      } else b.title=n+" sourced anchors in this window";
    });
  })();
  bindPills("[data-tf]",function(b){
    document.querySelectorAll("[data-tf]").forEach(function(o){o.removeAttribute("data-on");});
    b.setAttribute("data-on","1"); ST.days=parseInt(b.getAttribute("data-tf"),10);
  });
  bindPills("[data-res]",function(b){
    document.querySelectorAll("[data-res]").forEach(function(o){o.removeAttribute("data-on");});
    b.setAttribute("data-on","1");
    var r=b.getAttribute("data-res").split("x");
    ST.cols=parseInt(r[0],10); ST.rows=parseInt(r[1],10);
  });
  bindPills("[data-scheme]",function(b){
    document.querySelectorAll("[data-scheme]").forEach(function(o){o.removeAttribute("data-on");});
    b.setAttribute("data-on","1"); ST.scheme=b.getAttribute("data-scheme");
  });
  function syncLev(){
    var a=q("hm-lmin"), b=q("hm-lmax");
    if(a) a.value=ST.lmin; if(b) b.value=ST.lmax;
    document.querySelectorAll("[data-lrange]").forEach(function(o){
      var r=o.getAttribute("data-lrange").split("-");
      if(+r[0]===ST.lmin && +r[1]===ST.lmax) o.setAttribute("data-on","1");
      else o.removeAttribute("data-on");
    });
  }
  bindPills("[data-lrange]",function(b){
    var r=b.getAttribute("data-lrange").split("-");
    ST.lmin=+r[0]; ST.lmax=+r[1]; syncLev();
  });
  ["hm-lmin","hm-lmax"].forEach(function(id){
    var el=q(id); if(!el) return;
    el.addEventListener("change",function(){
      var v=parseInt(el.value,10);
      if(isNaN(v)) v = id==="hm-lmin" ? 2 : 125;
      v=Math.min(125,Math.max(2,v));
      if(id==="hm-lmin") ST.lmin=v; else ST.lmax=v;
      /* an inverted range is an empty model: keep at least one tier */
      if(ST.lmin>ST.lmax){ if(id==="hm-lmin") ST.lmax=ST.lmin; else ST.lmin=ST.lmax; }
      syncLev(); draw();
    });
  });
  var thr=q("hm-thr");
  if(thr) thr.addEventListener("input",function(){
    ST.thr=parseInt(thr.value,10)/100;
    setText("hm-thr-v",ST.thr.toFixed(2)); draw();
  });
  /* Zoom out was clamped at 1, so the chart could not be widened past the
     sourced window at all. The floor is now 0.2x. */
  function zoom(f){ ST.zoom=Math.min(25,Math.max(0.2,ST.zoom*f)); draw(); }
  var zi=q("hm-zin"), zo=q("hm-zout"), pu=q("hm-pan-up"), pd=q("hm-pan-dn"),
      rs=q("hm-reset");
  if(zi) zi.addEventListener("click",function(){zoom(1.5);});
  if(zo) zo.addEventListener("click",function(){zoom(1/1.5);});
  if(pu) pu.addEventListener("click",function(){ST.pan=Math.min(1,ST.pan+0.12/ST.zoom);draw();});
  if(pd) pd.addEventListener("click",function(){ST.pan=Math.max(-1,ST.pan-0.12/ST.zoom);draw();});
  var fit=q("hm-fit");
  if(fit) fit.addEventListener("click",function(){ST.zoom=1;ST.pan=0;draw();});
  if(rs) rs.addEventListener("click",function(){
    ST.zoom=1; ST.pan=0; ST.thr=0; ST.lmin=2; ST.lmax=125;
    ST.days=0; ST.cols=160; ST.rows=90; ST.scheme="viridis";
    if(thr){thr.value=0; setText("hm-thr-v","0.00");}
    document.querySelectorAll("[data-tf]").forEach(function(o){
      o.toggleAttribute("data-on", o.getAttribute("data-tf")==="0"); });
    document.querySelectorAll("[data-res]").forEach(function(o){
      o.toggleAttribute("data-on", o.getAttribute("data-res")==="160x90"); });
    document.querySelectorAll("[data-scheme]").forEach(function(o){
      o.toggleAttribute("data-on", o.getAttribute("data-scheme")==="viridis"); });
    syncLev(); draw();
  });

  /* drag to pan the price axis, as on a real chart */
  var dragging=false, lastY=0;
  cv.addEventListener("mousedown",function(ev){
    dragging=true; lastY=ev.clientY; cv.style.cursor="grabbing"; ev.preventDefault();
  });
  addEventListener("mouseup",function(){dragging=false; cv.style.cursor="grab";});
  addEventListener("mousemove",function(ev){
    if(!dragging) return;
    var dy=(ev.clientY-lastY)/Math.max(1,cv.getBoundingClientRect().height);
    lastY=ev.clientY;
    ST.pan=Math.max(-3,Math.min(3,ST.pan+dy/ST.zoom));
    draw();
  });
  cv.style.cursor="grab";
  /* scroll to zoom the price axis, as on a real chart */
  cv.addEventListener("wheel",function(ev){
    ev.preventDefault(); zoom(ev.deltaY<0?1.18:1/1.18);
  },{passive:false});
  bindPills("[data-ct]",function(b){
    document.querySelectorAll("[data-ct]").forEach(function(o){o.removeAttribute("data-on");});
    b.setAttribute("data-on","1"); ST.chart=b.getAttribute("data-ct");
  });

  /* ---- zoom from the price tags, the way a charting package does it -------
     Drag the price axis down to compress the scale, up to expand it; the wheel
     does the same in discrete steps. Without this the axis is decoration. */
  /* q("hm-price") again, deliberately: `price` inside draw() is function-local
     and referencing it here threw, which killed the whole controller. */
  var axis=q("hm-price");
  if(axis){
    axis.setAttribute("title","drag or scroll the price axis to rescale");
    var pdrag=false, pY=0;
    axis.addEventListener("mousedown",function(ev){
      pdrag=true; pY=ev.clientY; ev.preventDefault();
    });
    addEventListener("mouseup",function(){pdrag=false;});
    addEventListener("mousemove",function(ev){
      if(!pdrag) return;
      var dy=ev.clientY-pY; pY=ev.clientY;
      /* down widens the band (zoom out), up narrows it - matches every chart */
      if(dy) zoom(Math.exp(-dy/140));
    });
    axis.addEventListener("wheel",function(ev){
      ev.preventDefault(); zoom(ev.deltaY<0?1.12:1/1.12);
    },{passive:false});
  }

  /* ---- crosshair + readout ------------------------------------------------ */
  var hair=q("hm-hair"), tip=q("hm-tip");
  function nearest(x){
    var best=null, d=1e18;
    for(var i=0;i<LAST.length;i++){
      var dx=Math.abs(LAST[i].x-x);
      if(dx<d){d=dx; best=LAST[i];}
    }
    return best;
  }
  cv.addEventListener("mousemove",function(ev){
    if(!hair||!LAST.length) return;
    var r=cv.getBoundingClientRect();
    if(!r.width||!r.height) return;
    var sx=(ev.clientX-r.left)/r.width, sy=(ev.clientY-r.top)/r.height;
    hair.style.left=(sx*100)+"%"; hair.style.top=(sy*100)+"%"; hair.hidden=false;
    var pr=CUR.hi-(CUR.hi-CUR.lo)*sy;
    var n=nearest(sx*cv.width);
    if(tip&&n){
      tip.hidden=false;
      tip.style.left=(sx*100)+"%";
      tip.style.top=(sy*100)+"%";
      tip.setAttribute("data-flip", sx>0.62 ? "1" : "");
      tip.innerHTML="<b>"+fmt(pr)+"</b><i>cursor</i>"+
        "<b>"+fmt(n.price)+"</b><i>"+n.date.slice(0,10)+" "+n.date.slice(11,16)+"Z</i>"+
        "<u>"+n.source+" &middot; T"+n.tier+"</u>";
    }
  });
  cv.addEventListener("mouseleave",function(){
    if(hair) hair.hidden=true; if(tip) tip.hidden=true;
  });

  syncLev(); draw();
})();

/* ---- relative time on the geopolitical board, recomputed every tick ---- */
function relTime(){
  var now=Date.now();
  var els=document.querySelectorAll("[data-ago]");
  for(var i=0;i<els.length;i++){
    var t=Date.parse(els[i].getAttribute("data-ago"));
    if(isNaN(t)){els[i].textContent="UNKNOWN";continue;}
    var s=Math.max(0,Math.floor((now-t)/1000));
    var out;
    if(s<3600) out=Math.floor(s/60)+"m ago";
    else if(s<86400) out=Math.floor(s/3600)+"h ago";
    else out=Math.floor(s/86400)+"d "+Math.floor(s%86400/3600)+"h ago";
    els[i].textContent=out;
  }
}
relTime(); setInterval(relTime,30000);

/* ---- ambient field: tape, motes, sweep, ping ---- */
(function(){
  var c=q("fx");if(!c||!c.getContext)return;
  var ctx=c.getContext("2d");if(!ctx)return;
  var reduce=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;
  var W=0,H=0,dpr=1,N=300,layers=[],motes=[],streams=[],sweep=-0.3,
      ping=0,pingAt=0,ping2At=-570,t=0;   /* negative = phase offset, never ahead of t */
  var MOTE_HUES=["46,197,207","122,108,240","99,184,92","200,204,70",
                 "242,232,92","232,163,60"];

  /* Integer wavenumbers make the series exactly periodic over N, so rotating
     the ring scrolls it seamlessly and it can never drain off-screen. */
  function layer(seed,speed,alpha,hue){
    var p=[],k=[2,5,11,17],a=[0.15,0.08,0.045,0.025];
    for(var i=0;i<N;i++){
      var y=0.5;
      for(var j=0;j<4;j++){y+=a[j]*Math.sin(2*Math.PI*k[j]*i/N+seed*(j+1));}
      p.push(Math.max(0.05,Math.min(0.95,y)));
    }
    return {p:p,speed:speed,alpha:alpha,hue:hue,acc:0};
  }
  function seedStreams(){
    streams=[];
    var n=Math.min(16,Math.max(5,Math.round(innerWidth/140)));
    for(var i=0;i<n;i++){
      streams.push({x:Math.random(),y:Math.random(),len:0.05+Math.random()*0.16,
        v:0.0016+Math.random()*0.0042,w:0.6+Math.random()*1.1,
        h:MOTE_HUES[(Math.random()*MOTE_HUES.length)|0],a:0.10+Math.random()*0.18});
    }
  }
  function seedMotes(){
    motes=[];
    var n=Math.min(70,Math.max(24,Math.round(innerWidth/26)));
    for(var i=0;i<n;i++){
      motes.push({x:Math.random(),y:Math.random(),
        v:0.00006+Math.random()*0.00022,r:0.4+Math.random()*1.3,
        a:0.10+Math.random()*0.30,
        h:MOTE_HUES[(Math.random()*MOTE_HUES.length)|0]});
    }
  }
  function resize(){
    dpr=Math.min(window.devicePixelRatio||1,2);
    W=c.width=Math.max(1,Math.floor(innerWidth*dpr));
    H=c.height=Math.max(1,Math.floor(innerHeight*dpr));
    c.style.width=innerWidth+"px";c.style.height=innerHeight+"px";
    seedMotes();seedStreams();
  }
  function drawLayer(L){
    var seg=W/(N-1),i,x;
    ctx.beginPath();
    for(i=0;i<=N;i++){
      x=(i-L.acc)*seg;
      if(i===0){ctx.moveTo(x,L.p[0]*H);}
      else{ctx.lineTo(x,L.p[(i-1)%N]*H);ctx.lineTo(x,L.p[i%N]*H);}
    }
    ctx.strokeStyle=L.hue;ctx.globalAlpha=L.alpha;ctx.lineWidth=dpr;ctx.stroke();
    ctx.globalAlpha=1;
  }
  function frame(){
    t++;
    ctx.clearRect(0,0,W,H);
    ctx.fillStyle="#05060A";ctx.fillRect(0,0,W,H);

    /* drifting measurement grid */
    var gs=68*dpr, off=reduce?0:(t*0.12)%gs;
    ctx.strokeStyle="rgba(26,32,48,0.5)";ctx.lineWidth=1;
    for(var x=-gs+off;x<W;x+=gs){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,H);ctx.stroke();}
    for(var y=0;y<H;y+=gs){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke();}

    for(var i=0;i<layers.length;i++){
      var L=layers[i];
      if(!reduce){L.acc+=L.speed;while(L.acc>=1){L.p.push(L.p.shift());L.acc-=1;}}
      drawLayer(L);
    }

    /* rising motes */
    for(var m=0;m<motes.length;m++){
      var o=motes[m];
      if(!reduce){o.y-=o.v;if(o.y<-0.02){o.y=1.02;o.x=Math.random();}}
      ctx.beginPath();
      ctx.arc(o.x*W,o.y*H,o.r*dpr,0,6.283);
      ctx.fillStyle="rgba("+o.h+","+o.a+")";ctx.fill();
    }

    /* vertical data streams */
    for(var k=0;k<streams.length;k++){
      var st=streams[k];
      if(!reduce){st.y+=st.v;if(st.y-st.len>1){st.y=-0.02;st.x=Math.random();}}
      var gx=st.x*W, gy0=(st.y-st.len)*H, gy1=st.y*H;
      var lg=ctx.createLinearGradient(gx,gy0,gx,gy1);
      lg.addColorStop(0,"rgba("+st.h+",0)");
      lg.addColorStop(1,"rgba("+st.h+","+st.a+")");
      ctx.strokeStyle=lg;ctx.lineWidth=st.w*dpr;
      ctx.beginPath();ctx.moveTo(gx,gy0);ctx.lineTo(gx,gy1);ctx.stroke();
    }

    /* horizon glow */
    var hg=ctx.createLinearGradient(0,H*0.72,0,H);
    hg.addColorStop(0,"rgba(46,197,207,0)");
    hg.addColorStop(1,"rgba(46,197,207,0.045)");
    ctx.fillStyle=hg;ctx.fillRect(0,H*0.72,W,H*0.28);

    if(!reduce){
      /* two radar pings, opposite corners, different hues */
      if(t-pingAt>660){pingAt=t;}
      ping=(t-pingAt)/660;
      if(ping>=0&&ping<1){
        var rr=ping*Math.max(W,H)*1.15;
        ctx.beginPath();ctx.arc(W*0.06,H*0.02,rr,0,6.283);
        ctx.strokeStyle="rgba(46,197,207,"+(0.11*(1-ping))+")";
        ctx.lineWidth=1.5*dpr;ctx.stroke();
      }
      if(t-ping2At>900){ping2At=t;}
      var p2=(t-ping2At)/900;
      if(p2>=0&&p2<1){
        var r2=p2*Math.max(W,H)*1.25;
        ctx.beginPath();ctx.arc(W*0.97,H*0.85,r2,0,6.283);
        ctx.strokeStyle="rgba(122,108,240,"+(0.09*(1-p2))+")";
        ctx.lineWidth=1.3*dpr;ctx.stroke();
      }
      /* CRT sweep */
      sweep+=0.0014;if(sweep>1.3)sweep=-0.3;
      var sx=sweep*W,g=ctx.createLinearGradient(sx-190*dpr,0,sx+20*dpr,0);
      g.addColorStop(0,"rgba(46,197,207,0)");
      g.addColorStop(0.8,"rgba(46,197,207,0.035)");
      g.addColorStop(1,"rgba(46,197,207,0.11)");
      ctx.fillStyle=g;ctx.fillRect(sx-190*dpr,0,210*dpr,H);
      ctx.fillStyle="rgba(46,197,207,0.15)";ctx.fillRect(sx,0,dpr,H);
    }
  }
  /* The loop re-arms in a finally block: one bad frame must degrade a single
     frame, never stop the animation for the life of the page. */
  function loop(){
    try{ frame(); }
    catch(err){ if(window.console&&console.warn) console.warn("fx frame:",err); }
    finally{ if(!reduce) requestAnimationFrame(loop); }
  }
  layers=[layer(1.1,0.062,0.16,"#2EC5CF"),
          layer(3.7,0.040,0.115,"#7A6CF0"),
          layer(6.3,0.024,0.085,"#63B85C"),
          layer(9.1,0.014,0.06,"#C8CC46")];
  resize();loop();
  addEventListener("resize",function(){resize();if(reduce)frame();},{passive:true});
})();
})();
"""



# ---------------------------------------------------------------------------
# Component renderers
# ---------------------------------------------------------------------------

# Fear & Greed band edges as fractions of the 0-100 scale, with their colours.
FG_BANDS = ((0.00, 0.25, "#B0323C", "Extreme fear"), (0.25, 0.45, "#FF5C6C", "Fear"),
            (0.45, 0.55, "#E8B33C", "Neutral"), (0.55, 0.75, "#35D07F", "Greed"),
            (0.75, 1.00, "#1F9E5F", "Extreme greed"))


def _arc_point(f: float, r: float = 80.0, cx: float = 100.0, cy: float = 100.0):
    """Point on the upper semicircle at fraction f of the sweep (0 = left)."""
    import math
    a = f * math.pi
    return cx - r * math.cos(a), cy - r * math.sin(a)


def _arc_path(f0: float, f1: float, r: float = 80.0) -> str:
    x0, y0 = _arc_point(f0, r)
    x1, y1 = _arc_point(f1, r)
    large = 1 if (f1 - f0) > 0.5 else 0
    return f"M {x0:.2f} {y0:.2f} A {r:.0f} {r:.0f} 0 {large} 1 {x1:.2f} {y1:.2f}"


def _band_colour(f: float) -> str:
    for lo, hi, col, _ in FG_BANDS:
        if lo <= f <= hi:
            return col
    return "#E8B33C"


def render_gauge(g) -> str:
    """A meter, not a chart: one value on one bounded scale, direct-labelled."""
    f = max(0.0, min(1.0, g.pct))
    nx, ny = _arc_point(f, 62.0)
    col = _band_colour(f)
    segs = "".join(
        f'<path d="{_arc_path(lo, hi)}" fill="none" stroke="{col}" stroke-width="13" '
        f'stroke-linecap="butt" opacity="{0.95 if lo <= f <= hi else 0.22}"/>'
        for lo, hi, col, _ in FG_BANDS
    )
    ticks = ""
    for tf, tl in ((0.0, "0"), (0.5, "50"), (1.0, "100")):
        tx, ty = _arc_point(tf, 96.0)
        anchor = "start" if tf == 0 else ("end" if tf == 1 else "middle")
        ticks += (f'<text x="{tx:.1f}" y="{ty + 6:.1f}" text-anchor="{anchor}" '
                  f'fill="#3A4358" font-family="JetBrains Mono, monospace" '
                  f'font-size="10">{tl}</text>')
    return (
        f'<div class="gg">'
        f'<svg viewBox="0 0 200 118" role="img" aria-label="{e(g.label)}: {g.value:.0f} '
        f'of 100, {e(g.band)}">{segs}{ticks}'
        f'<line class="needle" x1="100" y1="100" x2="{nx:.2f}" y2="{ny:.2f}" '
        f'stroke="{col}" stroke-width="3.5" stroke-linecap="round"/>'
        f'<circle cx="100" cy="100" r="6" fill="#0C0F17" stroke="{col}" stroke-width="2.5"/>'
        f'</svg>'
        f'<span class="gv" style="color:{col}">{g.value:.0f}</span>'
        f'<span class="gb" style="color:{col}">{e(g.band)}</span>'
        f'<span class="gl">{e(g.label)}</span>'
        f'<span class="gs">{e(g.source)} &middot; T{g.tier} &middot; '
        f'{e(g.as_of[:16].replace("T", " "))}Z &middot; conf {g.confidence:.2f}</span>'
        f'</div>'
    )


def render_liquidations(snap) -> str:
    """Observed liquidations plus a computed leverage ladder.

    The two are visually and textually separated, because one is data and the
    other is arithmetic. Neither is an exchange heatmap and the page says so.
    """
    from .live import liquidation_ladder

    liq = snap.liquidations
    btc = snap.q("BTC")
    out = []

    if liq is not None:
        sp, lp = liq.short_pct, liq.long_pct
        out.append(
            f'<div class="spotline"><span>observed &middot; {e(liq.window)}</span>'
            f'<span>${liq.total_usd / 1e6:,.1f}m total</span></div>'
            f'<div class="liqbar">'
            f'<span class="ls" style="flex:0 0 {sp:.2f}%">SHORTS {sp:.1f}% '
            f'&middot; ${liq.short_usd / 1e6:,.0f}m</span>'
            f'<span class="ll" style="flex:0 0 {lp:.2f}%">LONGS {lp:.1f}%</span>'
            f'</div>'
        )
        if liq.asset_usd:
            out.append(
                f'<dl class="kv"><dt>{e(liq.asset_label)}</dt>'
                f'<dd>${liq.asset_usd / 1e6:,.1f}m'
                + (f' &middot; {liq.asset_short_pct:.0f}% short'
                   if liq.asset_short_pct else "")
                + f'</dd><dt>Longs</dt><dd>${liq.long_usd / 1e6:,.1f}m</dd>'
                f'<dt>Source</dt><dd>{e(liq.source)} &middot; T{liq.tier}</dd></dl>'
            )
        out.append(f'<p class="note">{e(liq.note)}</p>')
    else:
        out.append('<p class="note">Observed liquidations UNAVAILABLE in this snapshot.</p>')

    if btc:
        ladder = liquidation_ladder(btc.value)
        rows = []
        for r in ladder:
            frac = min(r["move_pct"] / 25.0, 1.0)
            w = 50.0 * frac
            rows.append(
                f'<div class="lr"><span class="lev">{r["leverage"]}&times;</span>'
                f'<span class="rng"><span class="seg dn" style="left:{50 - w:.2f}%;'
                f'width:{w:.2f}%"></span>'
                f'<span class="seg upl" style="left:50%;width:{w:.2f}%"></span>'
                f'<span class="mid"></span></span>'
                f'<span class="lev" style="color:var(--dim)">&plusmn;{r["move_pct"]:.0f}%</span>'
                f'</div>'
                f'<div class="lr" style="border-bottom:0;padding-top:0">'
                f'<span class="px dn">{r["long_liq"]:,.0f}</span>'
                f'<span class="rng" style="border:0;height:0"></span>'
                f'<span class="px up">{r["short_liq"]:,.0f}</span></div>'
            )
        out.append(
            f'<div class="spotline" style="margin-top:6px">'
            f'<span>computed ladder</span><span>spot {btc.value:,.0f} '
            f'&middot; {e(btc.as_of[11:16])}Z</span></div>'
            f'<div class="ladder">{"".join(rows)}</div>'
            f'<p class="note warn"><b>Computed, not observed.</b> These are the exact '
            f'liquidation prices for a position opened at spot &mdash; '
            f'price &times; (1 &minus; 1/N) for a long, price &times; (1 + 1/N) for a '
            f'short. They exclude maintenance margin and fees, so a venue triggers '
            f'marginally earlier. This is <b>not</b> a heatmap of where open interest '
            f'actually sits: that needs per-exchange position data this terminal does '
            f'not have, and it is not guessed.</p>'
        )
    return "".join(out)


def render_heatmap(snap) -> str:
    """CoinGlass-form heatmap with live controls.

    The grid is recomputed in the browser by a direct port of
    ``macro.live.liquidation_heatmap``; a cross-implementation test runs the two
    against each other so the controls cannot drift from the reference model.
    """
    if len(snap.price_anchors) < 2:
        return ('<p class="note">Heatmap UNAVAILABLE &mdash; needs at least two dated '
                'price anchors, and they are not interpolated into existence.</p>')

    tf = "".join(
        f'<button class="pill" data-tf="{d}"{" data-on=1" if d == 0 else ""}>'
        f'{"ALL" if d == 0 else str(d) + "D"}</button>'
        for d in (3, 7, 14, 21, 30, 0)
    )
    lev = "".join(
        f'<button class="pill" data-lrange="{a}-{b}"'
        f'{" data-on=1" if (a, b) == (2, 125) else ""}>{lbl}</button>'
        for a, b, lbl in ((2, 125, "ALL"), (2, 10, "LOW"), (10, 50, "MID"),
                          (50, 125, "HIGH"), (100, 125, "EXTREME"))
    )
    schemes = "".join(
        f'<button class="sw-btn" data-scheme="{k}" title="{k}"'
        f'{" data-on=1" if k == "viridis" else ""}>'
        f'<i style="background:linear-gradient(90deg,{",".join(v)})"></i></button>'
        for k, v in HEAT_RAMPS.items()
    )
    charts = "".join(
        f'<button class="pill" data-ct="{k}"{" data-on=1" if k == "candle" else ""}>'
        f'{lbl}</button>'
        for k, lbl in (("candle", "CANDLES"), ("bar", "OHLC BARS"),
                       ("area", "AREA"), ("line", "LINE"), ("off", "OFF"))
    )
    res = "".join(
        f'<button class="pill" data-res="{c}x{r}"{" data-on=1" if c == 160 else ""}>'
        f'{lbl}</button>'
        for c, r, lbl in ((60, 40, "COARSE"), (110, 64, "MED"), (160, 90, "FINE"),
                          (240, 130, "ULTRA"))
    )
    return (
        '<div class="hm-ctl">'
        f'<span class="ctl-g"><b>WINDOW</b>{tf}</span>'
        f'<span class="ctl-g"><b>LEVERAGE</b>{lev}'
        '<input id="hm-lmin" type="number" min="2" max="125" value="2" '
        'aria-label="Minimum leverage"><i class="ctl-x">&ndash;</i>'
        '<input id="hm-lmax" type="number" min="2" max="125" value="125" '
        'aria-label="Maximum leverage"><i class="ctl-v">&times;</i></span>'
        f'<span class="ctl-g"><b>GRID</b>{res}</span>'
        f'<span class="ctl-g"><b>SCHEME</b>{schemes}</span>'
        '<span class="ctl-g"><b>THRESHOLD</b>'
        '<input id="hm-thr" type="range" min="0" max="90" value="0" step="5" '
        'aria-label="Intensity threshold">'
        '<i id="hm-thr-v" class="ctl-v">0.00</i></span>'
        f'<span class="ctl-g"><b>PRICE</b>{charts}</span>'
        '<span class="ctl-g"><b>ZOOM</b>'
        '<button class="pill" id="hm-zin" title="Zoom in on price">+</button>'
        '<button class="pill" id="hm-zout" title="Zoom out">&minus;</button>'
        '<i id="hm-zv" class="ctl-v">1.00&times;</i>'
        '<button class="pill" id="hm-pan-up" title="Pan up">&uarr;</button>'
        '<button class="pill" id="hm-pan-dn" title="Pan down">&darr;</button>'
        '<button class="pill" id="hm-fit" title="Fit to the sourced window">FIT</button>'
        '<button class="pill" id="hm-reset">RESET</button></span>'
        '</div>'
        '<div class="hm-stage">'
        '<div class="hm-scale"><i id="hm-peak">&mdash;</i>'
        '<span class="hm-bar" id="hm-bar"></span><i>0</i></div>'
        '<div class="hm-field">'
        '<canvas class="hm" id="hm-canvas" width="1152" height="832" role="img" '
        'aria-label="Liquidation leverage density by price and time"></canvas>'
        '<i class="hm-hair" id="hm-hair" hidden></i>'
        '<div class="hm-tip" id="hm-tip" hidden></div>'
        '</div>'
        '<div class="hm-price" id="hm-price"></div>'
        '<div class="hm-time" id="hm-time"></div>'
        '</div>'
        '<div class="hm-key">'
        '<i><span class="sw" style="background:#EAF6FF"></span>up on the previous '
        'observation</i>'
        '<i><span class="sw" style="background:#FF4D6D"></span>down on it</i>'
        '<i><span class="sw" style="background:var(--gold)"></span>body spans '
        'observation to observation &mdash; the intrabar range was never observed, '
        'so no wick is drawn beyond it</i>'
        '<i id="hm-meta">&mdash;</i></div>'
        '<p class="hm-hint">drag the field to pan &middot; drag or scroll the price '
        'tags to rescale &middot; hover for the reading &middot; every control '
        'recomputes the model</p>'
        '<p class="note warn"><b>Computed by the published method, on real prices.</b> '
        'At each observed price, positions opened there liquidate at '
        'price&times;(1&minus;1/N) and price&times;(1+1/N); those levels stay pending '
        'until price sweeps through them. Between two observations nothing is known, '
        'so the field is held and no price is ever interpolated. '
        'Each candle body spans one observation to the next, which is exactly what '
        'was observed; the intrabar high and low were never sourced, so no wick is '
        'drawn past the body and no OHLC range is invented. '
        'It is <b>not</b> open-interest weighted: that needs per-exchange position '
        'data. Every control below recomputes the model rather than restyling a '
        'picture of it.</p>'
    )


def render_equities(snap) -> str:
    if not snap.equities:
        return '<p class="note">No equity data in this snapshot.</p>'
    cells = []
    for x in sorted(snap.equities,
                    key=lambda v: -(v.mktcap_usd or 0)):
        cap = (f"${x.mktcap_usd / 1e12:,.2f}T" if x.mktcap_usd and x.mktcap_usd >= 1e12
               else (f"${x.mktcap_usd / 1e9:,.0f}B" if x.mktcap_usd else "cap UNKNOWN"))
        if x.change_pct is None:
            mv, cls = "move UNKNOWN", "flat"
        else:
            cls = "up" if x.change_pct > 0 else ("down" if x.change_pct < 0 else "flat")
            arrow = "\u25b2" if x.change_pct > 0 else ("\u25bc" if x.change_pct < 0 else "\u25ac")
            mv = f"{arrow} {abs(x.change_pct):.2f}%"
        cells.append(
            f'<div class="eqc" title="{e(x.note)}"><span class="eqt">{e(x.ticker)}</span>'
            f'<span class="nm2">{e(x.name)}</span>'
            f'<span class="cap">{e(cap)}</span>'
            f'<span class="mv {cls}">{mv}</span>'
            f'<span class="sr">{e(x.source)} &middot; T{x.tier} &middot; '
            f'{e(x.as_of[11:16])}Z</span></div>'
        )
    return f'<div class="eq">{"".join(cells)}</div>'


def render_earnings(snap) -> str:
    if not snap.earnings:
        return '<p class="note">No earnings events in this snapshot.</p>'
    rows = []
    order = {"SCHEDULED": 0, "REPORTED": 1}
    for x in sorted(snap.earnings, key=lambda v: (order.get(v.status, 2), v.when or "z")):
        if x.status == "REPORTED":
            cd = f'<span class="ecd done">REPORTED</span>'
        elif x.when:
            # day granularity unless the hour is actually published
            cd = (f'<span class="ecd" data-when="{e(x.when)}">&mdash;</span>'
                  if x.time_confirmed else
                  f'<span class="ecd" data-days="{e(x.when)}">&mdash;</span>')
        else:
            cd = f'<span class="ecd win">{e(x.window)}</span>'
        when_txt = (f'{x.when[:10]}' if x.when else e(x.window))
        prec = ("exact time published" if x.time_confirmed else
                ("date published, hour not" if x.when else "window only, no date"))
        rows.append(
            f'<div class="er"><span class="etk">{e(x.ticker)}</span>'
            f'<span class="enm">{e(x.name)} '
            f'<span class="ses">{e(x.session)}</span></span>{cd}'
            f'<span class="esub">{e(when_txt)} &middot; {prec} &middot; '
            f'{e(x.source)} &middot; T{x.tier} &middot; '
            f'<a href="{e(x.url)}" target="_blank" rel="noopener noreferrer">source</a>'
            + (f' &middot; {e(x.note)}' if x.note else "")
            + '</span></div>'
        )
    return f'<div class="earn">{"".join(rows)}</div>'


def render_geo(snap) -> str:
    if not snap.geo:
        return '<p class="note">No geopolitical items in this snapshot.</p>'
    rows = []
    for g in snap.geo:
        col = ("var(--down)" if g.severity >= 85 else
               "var(--gold)" if g.severity >= 70 else "var(--ink-2)")
        st = g.status.upper()
        cls = "esc" if "ESCALAT" in st else ("act" if "ACTIVE" in st or "TODAY" in st
                                             else "ong")
        chips = "".join(f'<span class="chip">{e(a)}</span>' for a in g.assets)
        link = (f'<a href="{e(g.url)}" target="_blank" rel="noopener noreferrer">source</a>'
                if g.url else "")
        rows.append(
            f'<article class="ge"><div class="sev" style="color:{col}">{g.severity}'
            f'<small>SEVERITY</small></div><div>'
            f'<h4>{e(g.headline)}</h4>'
            f'<p class="ch">{e(g.channel)}</p>'
            f'<div class="meta"><span class="stat {cls}">{e(g.status)}</span>'
            f'<span class="chip">{e(g.region)}</span>'
            f'<span class="t t{g.tier}">T{g.tier}</span><span>{e(g.source)}</span>'
            f'{link}{chips}</div></div>'
            f'<div class="when"><span class="abs">{e(g.as_of[5:10])} '
            f'{e(g.as_of[11:16])}Z</span>'
            f'<span class="ago" data-ago="{e(g.as_of)}">&mdash;</span></div>'
            f'</article>'
        )
    return f'<div class="geo">{"".join(rows)}</div>'


def render_flows(snap) -> str:
    if not snap.flows:
        return '<p class="note">No flow data in this snapshot.</p>'
    rows = []
    for f in snap.flows:
        d = str(f.get("direction", "in"))
        rows.append(
            f'<div class="fl"><span class="fn">{e(f.get("label", ""))}</span>'
            f'<span class="fv {d}">{e(f.get("value", ""))}</span>'
            f'<span class="fw">{e(f.get("window", ""))} &middot; '
            f'{e(f.get("source", ""))} &middot; T{f.get("tier", 3)} &middot; '
            f'{e(f.get("note", ""))}</span></div>'
        )
    return f'<div class="flows">{"".join(rows)}</div>'


def render_squawk(snap) -> str:
    """Timestamped wire, newest first, with an impact rail - a squawk, not a blog."""
    if not snap.headlines:
        return '<p class="note">No headlines in this snapshot.</p>'
    items = sorted(snap.headlines, key=lambda h: (h.published, h.impact), reverse=True)
    rows = []
    for h in items:
        col = ("var(--down)" if h.impact >= 85 else
               "var(--gold)" if h.impact >= 65 else "var(--ink-2)")
        link = (f'<a href="{e(h.url)}" target="_blank" rel="noopener noreferrer">source</a>'
                if h.url else "")
        chips = "".join(f'<span class="chip">{e(a)}</span>' for a in h.assets)
        flag = ('<span class="chip" style="color:var(--up);border-color:var(--up-dim)">'
                'PRIMARY</span>' if h.primary_confirmed else
                '<span class="chip" style="color:var(--gold);'
                'border-color:var(--gold-dim)">REPORTED</span>')
        rows.append(
            f'<article class="sqr"><span class="sqt">{e(h.published[5:10])}<br>'
            f'{e(h.published[11:16])}Z</span>'
            f'<span class="sqrail" style="background:{col}"></span>'
            f'<span class="sqb"><h3>{e(h.title)}</h3>'
            + (f'<p>{e(h.summary)}</p>' if h.summary else "")
            + f'<span class="meta"><span class="imp" style="color:{col};font-size:13px;'
            f'display:inline">{h.impact}</span><span class="t t{h.tier}">T{h.tier}</span>'
            f'<span>{e(h.source)}</span>{flag}{link}{chips}</span></span></article>'
        )
    return f'<div class="sq">{"".join(rows)}</div>'


def _fmt(v: float, unit: str) -> str:
    if unit in ("pct",):
        return f"{v:.2f}%"
    if unit in ("usd_bbl", "usd_oz", "usd"):
        return f"{v:,.2f}" if v < 1000 else f"{v:,.0f}"
    if unit == "index":
        return f"{v:,.2f}"
    return f"{v:,.2f}"


def _delta(q) -> tuple[str, str]:
    if q.change is None:
        return "", "flat"
    cls = "up" if q.change > 0 else ("down" if q.change < 0 else "flat")
    arrow = "▲" if q.change > 0 else ("▼" if q.change < 0 else "▬")
    if q.change_unit == "bp":
        txt = f"{arrow} {abs(q.change):.0f}bp"
    elif q.change_unit == "pct":
        txt = f"{arrow} {abs(q.change):.2f}%"
    else:
        txt = f"{arrow} {abs(q.change):.2f}"
    return txt, cls


ORDER = ("US2Y", "US10Y", "SPX", "DJIA", "NDX", "VIX", "DXY", "BRENT", "WTI", "GOLD", "BTC")


def render(snap: Snapshot, standalone: bool = True) -> str:
    quotes = [snap.quotes[k] for k in ORDER if k in snap.quotes]
    quotes += [v for k, v in snap.quotes.items() if k not in ORDER]

    # --- ticker (doubled so the marquee loops seamlessly at -50%) ---------
    def tk(q) -> str:
        txt, cls = _delta(q)
        return (f'<div class="tk"><span class="s">{e(q.label or q.key)}</span>'
                f'<span class="v">{e(_fmt(q.value, q.unit))}</span>'
                f'<span class="d {cls}">{txt}</span></div>')
    tape = "".join(tk(q) for q in quotes)

    # --- quote grid -------------------------------------------------------
    cells = []
    for q in quotes:
        txt, cls = _delta(q)
        bar = "var(--up)" if q.confidence >= 0.85 else (
            "var(--gold)" if q.confidence >= 0.7 else "var(--down)")
        cells.append(
            f'<div class="q" title="{e(q.note or q.label)}">'
            f'<span class="conf" style="background:{bar}"></span>'
            f'<span class="lab">{e(q.label or q.key)}<span class="t t{q.tier}">T{q.tier}</span></span>'
            f'<span class="val">{e(_fmt(q.value, q.unit))}</span>'
            f'<span class="dlt {cls}">{txt or "&mdash;"}</span>'
            f'<span class="src">{e(q.source)} &middot; {e(q.as_of[11:16])}Z '
            f'&middot; conf {q.confidence:.2f}</span></div>'
        )
    # Twelfth cell: the 2s10s spread. Derived, marked as such, and inheriting the
    # weaker of its two legs' confidence - never presented as a quoted price.
    two_q, ten_q = snap.q("US2Y"), snap.q("US10Y")
    if two_q and ten_q:
        spread_bp = (ten_q.value - two_q.value) * 100
        s_cls = "up" if spread_bp > 0 else "down"
        s_conf = min(two_q.confidence, ten_q.confidence)
        s_tier = max(two_q.tier, ten_q.tier)
        bar = "var(--up)" if s_conf >= 0.85 else (
            "var(--gold)" if s_conf >= 0.7 else "var(--down)")
        cells.append(
            '<div class="q derived" title="Computed from the two carried yields; '
            'inherits the weaker leg\'s confidence.">'
            f'<span class="conf" style="background:{bar}"></span>'
            f'<span class="lab">2s10s <span class="t t{s_tier}">DERIVED</span></span>'
            f'<span class="val">{spread_bp:+.0f} bp</span>'
            f'<span class="dlt {s_cls}">'
            f'{"positive" if spread_bp > 0 else "inverted"}</span>'
            f'<span class="src">computed &middot; UST 2Y &minus; 10Y &middot; '
            f'conf {s_conf:.2f}</span></div>'
        )
    grid = "".join(cells)

    # --- derived curve ----------------------------------------------------
    two, ten = snap.q("US2Y"), snap.q("US10Y")
    if two and ten:
        spread = (ten.value - two.value) * 100
        shape = "bear flattening" if (two.change or 0) > (ten.change or 0) else "steepening"
        curve = (
            f'<dl class="kv"><dt>2s10s</dt><dd>{spread:+.0f} bp '
            f'<span class="{"up" if spread > 0 else "down"}">'
            f'({"positive" if spread > 0 else "inverted"})</span></dd>'
            f'<dt>2Y move</dt><dd>{(two.change or 0):+.0f} bp</dd>'
            f'<dt>10Y move</dt><dd>{(ten.change or 0):+.0f} bp</dd>'
            f'<dt>Shape</dt><dd>{shape}</dd></dl>'
            f'<p class="note"><b>Derived, not quoted.</b> The spread is computed from the '
            f'two carried yields, so it inherits their confidence &mdash; the 2Y is the '
            f'weaker leg here.</p>'
        )
    else:
        curve = '<p class="note">2s10s UNAVAILABLE &mdash; both legs are required.</p>'

    # --- news: rendered by render_squawk() ---
    tier_mix = {}
    for _q in snap.quotes.values():
        tier_mix[_q.tier] = tier_mix.get(_q.tier, 0) + 1
    src_mix = " ".join(f"T{t}:{tier_mix[t]}" for t in sorted(tier_mix))

    squawk = render_squawk(snap)
    gauges_html = ("".join(render_gauge(g) for g in snap.gauges.values())
                   or '<p class="note">No sentiment gauges in this snapshot.</p>')
    liq_html = render_liquidations(snap)
    heat_html = render_heatmap(snap)
    eq_html = render_equities(snap)
    earn_html = render_earnings(snap)
    geo_html = render_geo(snap)
    flows_html = render_flows(snap)

    # --- releases ---------------------------------------------------------
    rel = []
    for r in snap.releases:
        rel.append(
            f'<div class="rl"><span class="nm">{e(r.get("label", ""))} '
            f'<span class="t t{r.get("tier", 1)}">T{r.get("tier", 1)}</span></span>'
            f'<span class="cd" data-when="{e(r.get("when", ""))}">&mdash;</span>'
            f'<span class="sub">{e(r.get("agency", ""))} &middot; '
            f'{e(r.get("when", "")[:16].replace("T", " "))}Z &middot; first public carrier: '
            f'<a href="{e(r.get("url", ""))}" target="_blank" rel="noopener noreferrer">'
            f'{e(r.get("url", "")[:64])}</a>'
            + (f' &middot; {e(r.get("note", ""))}' if r.get("note") else "")
            + '</span></div>'
        )
    releases = "".join(rel)

    # --- reaction map for the live catalyst -------------------------------
    regime = MacroRegime.INFLATION_DOMINANT if "INFLATION" in snap.regime else (
        MacroRegime.GROWTH_DOMINANT if "GROWTH" in snap.regime else MacroRegime.UNKNOWN)
    rmap = build_matrix(Impulse.GROWTH_STRONGER, regime, magnitude=2.0,
                        scenario_label="August payrolls +162k vs +53k expected")
    def dir_class(arrow: str) -> str:
        if arrow.startswith("^"):
            return "up"
        if arrow.startswith("v"):
            return "down"
        return "flat"

    rrows = "".join(
        '<tr><td style="color:var(--ink)">' + e(c.asset) + "</td>"
        + '<td class="arrow ' + dir_class(c.direction.arrow) + '">'
        + e(c.direction.arrow) + "</td>"
        + '<td style="font-variant-numeric:tabular-nums">'
        + f"{c.confidence:.2f}" + "</td>"
        + "<td>" + e(c.mechanism) + "</td></tr>"
        for c in rmap.cells
    )
    chain = "".join(f"<li>{e(s)}</li>" for s in rmap.chain)

    # --- policy -----------------------------------------------------------
    p = snap.policy
    fed, ecb, infl, lab = (p.get("fed", {}), p.get("ecb", {}),
                           p.get("inflation", {}), p.get("labor", {}))
    def kv(d: dict, keys: tuple[tuple[str, str], ...]) -> str:
        return "".join(f"<dt>{e(a)}</dt><dd>{e(d.get(b, 'UNKNOWN'))}</dd>" for a, b in keys)

    # Field lists are built outside the f-strings: an f-string expression cannot
    # be split across adjacent literals, which is a silent SyntaxError trap.
    fed_fields = (("Target", "target"), ("Last", "last_action"),
                  ("Dissents", "dissents"), ("Chair", "chair"),
                  ("Priced", "market_priced"))
    ecb_fields = (("Deposit", "target"), ("Last", "last_action"),
                  ("Chair", "chair"), ("Priced", "market_priced"))
    infl_fields = (("US CPI y/y", "us_cpi_yoy"), ("US core y/y", "us_core_cpi_yoy"),
                   ("US CPI m/m", "us_cpi_mom"), ("Peak", "peak"),
                   ("EZ HICP", "ez_hicp_yoy"))
    lab_fields = (("Payrolls", "nfp"), ("Unemployment", "unemployment"))

    policy = f'<dl class="kv">{kv(fed, fed_fields)}</dl>'
    ecb_html = f'<dl class="kv">{kv(ecb, ecb_fields)}</dl>'
    infl_html = (f'<dl class="kv">{kv(infl, infl_fields)}</dl>'
                 f'<dl class="kv">{kv(lab, lab_fields)}</dl>')

    conflicts = "".join(f'<p class="note warn">{e(c)}</p>' for c in snap.conflicts)
    errors = "".join(f'<p class="note bad">{e(x)}</p>' for x in snap.errors)

    audit = "".join(
        f'<tr><td style="color:var(--ink)">{e(q.label or q.key)}</td>'
        f'<td><span class="t t{q.tier}">T{q.tier}</span></td>'
        f'<td>{e(q.source)}</td><td>{e(q.as_of.replace("T", " ").rstrip("Z"))}Z</td>'
        f'<td style="font-variant-numeric:tabular-nums">{q.confidence:.2f}</td></tr>'
        for q in quotes
    )

    # Age is reported from the NEWEST OBSERVATION, not from when the scan ran.
    # A scan that reaches nothing still updates `captured`, so an age measured
    # from it goes to zero while the data underneath is a day old - the page
    # would look fresher than it is, which is the one thing it must never do.
    _stamps = [q.as_of for q in snap.quotes.values()]
    _stamps += [h.published for h in snap.headlines]
    _stamps += [a.date for a in snap.price_anchors]
    _stamps += [x.as_of for x in snap.equities]
    _stamps = [t for t in _stamps if isinstance(t, str) and t.endswith("Z")]
    newest = max(_stamps) if _stamps else snap.captured

    payload = json.dumps({
        "captured": snap.captured,
        "newest": newest,
        "ramps": {k: list(v) for k, v in HEAT_RAMPS.items()},
        "window": snap.btc_window or {},
        # Sorted here, not merely by authoring luck: windowed() and anchorsIn()
        # both read anchors[len-1] as the latest observation, and the scanner
        # appends in arrival order, not date order.
        "anchors": [{"date": a.date, "price": a.price, "source": a.source,
                     "tier": a.tier}
                    for a in sorted(snap.price_anchors, key=lambda a: a.date)],
    }, ensure_ascii=False).replace("</", "<\\/")

    head = (f'<title>Macro Desk Live</title>\n'
            f'<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            f'<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            f'<link rel="stylesheet" href="{FONTS}">\n'
            f'<style>{CSS}</style>')

    body = f"""<canvas id="fx" aria-hidden="true"></canvas>
<div class="aurora" aria-hidden="true"></div>
<div class="mesh" aria-hidden="true"></div>
<div class="sweep" aria-hidden="true"></div>
<div class="veil" aria-hidden="true"></div>
<div class="scan" aria-hidden="true"></div>

<div class="shell">
<header class="top">
  <div class="top-in">
    <div class="logo">
      <h1>Macro Desk</h1>
      <span class="tier">Cross-asset &middot; Rates &middot; Energy &middot; Crypto</span>
    </div>
    <div class="hud">
      <div class="cell"><span>Feed state</span>
        <b><i class="pulse" id="dot"></i><span id="state">&mdash;</span></b></div>
      <div class="cell"><span>Data age</span><b id="age">&mdash;</b></div>
      <div class="cell"><span>Session</span><b id="sess">&mdash;</b></div>
      <div class="cell"><span>Clock</span><b id="clk">&mdash;</b></div>
      <div class="cell"><span>Regime</span><b style="color:var(--gold)">{e(snap.regime)}</b></div>
    </div>
  </div>
  <div class="tape"><div class="tape-run">{tape}{tape}</div></div>
  <div class="cmdbar">
    <span class="fk"><b>F1</b> BOARD</span>
    <span class="fk"><b>F2</b> SQUAWK</span>
    <span class="fk"><b>F3</b> HEAT</span>
    <span class="fk"><b>F4</b> GEO</span>
    <span class="fk"><b>F5</b> RATES</span>
    <span class="fk"><b>F6</b> FLOW</span>
    <span class="fk"><b>F7</b> AUDIT</span>
    <span class="prompt"><span class="caret"></span>
      <span>type a mnemonic &mdash; panels below are the resident layout</span></span>
  </div>
</header>

<noscript><span class="ns">Clocks, countdowns and the data-age indicator are computed
live in the browser. Without JavaScript the market data below still renders, but every
timing field stays blank.</span></noscript>

<main>

  <section class="card c12">
    <h2>Cross-asset board <em>captured {e(snap.captured.replace("T", " ").rstrip("Z"))}Z &middot; every cell carries source, tier and time</em></h2>
    <div class="bd flush"><div class="qgrid">{grid}</div></div>
  </section>

  <section class="card c8">
    <h2>Squawk <em>timestamped wire &middot; newest first &middot; impact rail</em></h2>
    <div class="bd flush">{squawk}</div>
  </section>

  <section class="card c4">
    <h2>Sentiment <em>fear &amp; greed</em></h2>
    <div class="bd">
      <div class="gauges">{gauges_html}</div>
      <p class="note"><b>The divergence is the signal.</b> Equities and crypto are
      reading different clocks: crypto priced the pre-payrolls dovish story and the
      ETF bid, equities closed on the post-payrolls hawkish one. Two sentiment gauges
      pointing opposite ways inside one session is a positioning fact, not a
      contradiction.</p>
    </div>
  </section>

  <section class="card c12">
    <h2>BTC liquidation heatmap <em>price &times; time &middot; leverage density &middot; every control recomputes the model</em></h2>
    <div class="bd">{heat_html}</div>
  </section>

  <section class="card c5">
    <h2>Liquidations <em>observed + computed ladder</em></h2>
    <div class="bd">{liq_html}</div>
  </section>

  <section class="card c7">
    <h2>Geopolitical board <em>event &rarr; channel &rarr; asset &middot; with time of occurrence</em></h2>
    <div class="bd flush" style="padding:0 13px">{geo_html}</div>
  </section>

  <section class="card c7">
    <h2>Mega-cap board <em>largest listings by market value</em></h2>
    <div class="bd flush"><div style="padding:0">{eq_html}</div></div>
  </section>

  <section class="card c5">
    <h2>Earnings <em>countdown at the precision the source supports</em></h2>
    <div class="bd">{earn_html}
      <p class="note">A published <b>date</b> gets a day countdown; a published
      <b>hour</b> would get a clock. Where only a week is known there is no
      countdown at all &mdash; an invented hour on an earnings print is exactly the
      kind of false precision that gets someone positioned into the wrong session.</p>
    </div>
  </section>

  <section class="card c4">
    <h2>Next primary releases <em>countdown to the public instant</em></h2>
    <div class="bd">
      <div class="rel">{releases}</div>
      <p class="note"><b>This is the latency edge, and it is legal and public.</b>
      A statistical release is public at the agency URL the moment the embargo lifts,
      typically before wire coverage clears. The countdown targets that instant and
      names the page that carries it first &mdash; no privileged access is claimed
      or required.</p>
    </div>
  </section>

  <section class="card c4">
    <h2>Regime <em>established from the tape</em></h2>
    <div class="bd">
      <p class="reg">{e(snap.regime)}</p>
      <p class="note">{e(snap.regime_basis)}</p>
    </div>
  </section>

  <section class="card c4">
    <h2>Flows <em>where capital actually moved</em></h2>
    <div class="bd">{flows_html}
      <p class="note">Flow beats narrative. A price that rises on outflows is a
      warning; a price that falls on inflows is accumulation. Neither is assumed
      here &mdash; both legs are shown.</p>
    </div>
  </section>

  <section class="card c4">
    <h2>US curve <em>derived</em></h2>
    <div class="bd">{curve}</div>
  </section>

  <section class="card c4">
    <h2>Policy <em>Federal Reserve</em></h2>
    <div class="bd">{policy}
      <p class="note">Dissents pointing at a <b>hike</b> rather than a cut is the
      clearest single signal of which regime is in force.</p>
    </div>
  </section>

  <section class="card c4">
    <h2>Policy <em>ECB</em></h2>
    <div class="bd">{ecb_html}
      <p class="note">Euro-area inflation is re-accelerating while the energy shock
      runs. Divergence between a hiking ECB and a Fed on hold is the EURUSD trade.</p>
    </div>
  </section>

  <section class="card c12">
    <h2>Inflation &amp; labour <em>last prints, primary sourced</em></h2>
    <div class="bd" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px">
      {infl_html}
    </div>
  </section>

  <section class="card c12">
    <h2>Live catalyst &mdash; cross-asset transmission <em>{e(rmap.scenario)}</em></h2>
    <div class="bd">
      <ol style="margin:0;padding-left:22px;font-size:13.5px;color:var(--ink-2);
        display:flex;flex-direction:column;gap:5px">{chain}</ol>
      <div class="scroll" style="max-height:none"><table>
        <thead><tr><th style="width:13%">Asset</th><th style="width:6%">Dir</th>
        <th style="width:8%">Conf</th><th>Mechanism</th></tr></thead>
        <tbody>{rrows}</tbody></table></div>
      <p class="note"><b>Derived from the regime, not from a correlation table.</b>
      Under a growth-dominant regime the equity leg of this same payrolls beat would
      invert. That is why the regime is established before any direction is assigned.</p>
    </div>
  </section>

  <section class="card c7">
    <h2>Source &amp; freshness audit <em>every number on this page</em></h2>
    <div class="bd flush"><div class="scroll"><table>
      <thead><tr><th>Field</th><th>Tier</th><th>Source</th><th>As of</th><th>Conf</th></tr></thead>
      <tbody>{audit}</tbody></table></div></div>
  </section>

  <section class="card c5">
    <h2>Integrity <em>conflicts and corrections are shown, not resolved away</em></h2>
    <div class="bd">{conflicts}{errors}
      <p class="note">Where two outlets disagreed, the higher tier is carried at
      reduced confidence and the disagreement is printed. Where an earlier value was
      simply wrong, the correction is recorded rather than erased. The alternative
      &mdash; silently picking the more convenient figure &mdash; is how a terminal
      starts lying to its operator.</p>
    </div>
  </section>

</main>

<div class="statusbar">
  <span>SRC <b id="sb-src">{e(src_mix)}</b></span>
  <span>QUOTES <b>{len(snap.quotes)}</b></span>
  <span>WIRE <b>{len(snap.headlines)}</b></span>
  <span>GEO <b>{len(snap.geo)}</b></span>
  <span>CONFLICTS <b>{len(snap.conflicts)}</b></span>
  <span>REGIME <b>{e(snap.regime)}</b></span>
  <span>AGE <b id="sb-age">&mdash;</b></span>
  <span>UTC <b id="sb-clk">&mdash;</b></span>
</div>

<footer>
  <strong>What is live and what is not.</strong> The clock, the session state, the
  data-age counter and every release countdown are computed in your browser and are
  genuinely live. The market data is a <em>captured snapshot</em> stamped
  {e(snap.captured.replace("T", " ").rstrip("Z"))}Z &mdash; the header says SNAPSHOT
  and the age counter climbs, so the page can never look fresher than it is. Continuous
  refresh runs from <code>python -m macro live --daemon</code>, which polls the primary
  agency endpoints listed above and regenerates this page each cycle. Nothing here is
  investment advice.
</footer>
</div>

<script>window.__TERM__={payload};</script>
<script>{JS}</script>"""

    if not standalone:
        return head + "\n" + body + "\n"
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<meta name="description" content="Institutional macro terminal: cross-asset '
        'board, tiered news feed and primary-release countdowns, every figure carrying '
        'its source, tier and capture time.">\n'
        + head + "\n</head>\n<body>\n" + body + "\n</body>\n</html>\n"
    )


def main(out: str = "board/macro-desk-live.html", snapshot: str = "state/snapshot.json") -> int:
    import os
    from . import live as live_mod
    from . import seed as seed_mod

    snap = live_mod.load(snapshot)
    if snap is None:
        snap = seed_mod.build()
        live_mod.save(snap, snapshot)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    doc = render(snap)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(doc)
    frag = os.path.join(os.path.dirname(out) or ".", "macro-desk-fragment.html")
    with open(frag, "w", encoding="utf-8") as fh:
        fh.write(render(snap, standalone=False))
    print(f"wrote {out} ({len(doc.encode('utf-8')):,} bytes) from {snapshot}")
    print(f"  {len(snap.quotes)} quotes, {len(snap.headlines)} headlines, "
          f"{len(snap.releases)} scheduled releases, captured {snap.captured}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

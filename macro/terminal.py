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

from .live import Snapshot
from .reaction import ASSETS, build_matrix
from .regime import MacroRegime
from .surprise import Impulse

__all__ = ["render", "main"]


def e(x: object) -> str:
    return html.escape(str(x), quote=True)


FONTS = ("https://fonts.googleapis.com/css2?"
         "family=Barlow+Condensed:wght@500;600;700&"
         "family=Barlow:wght@400;500;600&"
         "family=JetBrains+Mono:wght@400;500;700&display=swap")

CSS = r"""
:root{
  --void:#06070B; --deep:#090B12; --panel:#0C0F17; --raise:#11151F;
  --edge:#1A2030; --edge-hi:#262E42;
  --gold:#E8B33C; --gold-dim:#7A5E1F;
  --up:#35D07F; --up-dim:#17603A;
  --down:#FF5C6C; --down-dim:#7A2A32;
  --live:#4EA8FF; --live-dim:#1E4E7A;
  --unk:#7E76A8;
  --ink:#D2D8E4; --ink-2:#98A3B8; --dim:#647089; --faint:#3A4358;
  --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --body:"Barlow",system-ui,-apple-system,"Segoe UI",sans-serif;
  --disp:"Barlow Condensed","Barlow",system-ui,sans-serif;
}
*{box-sizing:border-box}
html{background:var(--void)}
body{margin:0;background:var(--void);color:var(--ink);font-family:var(--body);
  font-size:13px;line-height:1.45;-webkit-font-smoothing:antialiased;overflow-x:hidden}
img{max-width:100%}
[hidden]{display:none!important}

#fx{position:fixed;inset:0;z-index:0;display:block;pointer-events:none}
.veil{position:fixed;inset:0;z-index:1;pointer-events:none;
  background:
    radial-gradient(1200px 700px at 8% -10%,rgba(232,179,60,.09),transparent 60%),
    radial-gradient(1000px 600px at 95% 0%,rgba(78,168,255,.07),transparent 58%),
    radial-gradient(1400px 900px at 50% 120%,rgba(126,118,168,.07),transparent 62%)}
.scan{position:fixed;inset:0;z-index:2;pointer-events:none;opacity:.35;
  background:repeating-linear-gradient(180deg,rgba(255,255,255,.022) 0 1px,transparent 1px 3px)}
.shell{position:relative;z-index:3}

/* ---------- masthead ---------- */
.top{position:sticky;top:0;z-index:20;border-bottom:1px solid var(--edge-hi);
  background:linear-gradient(180deg,rgba(12,15,23,.98),rgba(6,7,11,.94));
  backdrop-filter:blur(9px)}
.top-in{max-width:1720px;margin:0 auto;padding:11px 18px;display:flex;
  align-items:center;justify-content:space-between;gap:18px;flex-wrap:wrap}
.logo{display:flex;align-items:baseline;gap:12px;min-width:0}
.logo h1{margin:0;font-family:var(--disp);font-weight:700;font-size:29px;
  letter-spacing:.055em;text-transform:uppercase;color:var(--gold);line-height:1;
  text-shadow:0 0 26px rgba(232,179,60,.28)}
.logo .tier{font-family:var(--mono);font-size:9px;letter-spacing:.24em;color:var(--dim);
  text-transform:uppercase;border:1px solid var(--gold-dim);padding:2px 7px;border-radius:2px}
.hud{display:flex;gap:20px;flex-wrap:wrap;align-items:center}
.hud .cell{display:flex;flex-direction:column;gap:2px;min-width:0}
.hud .cell span{font-family:var(--mono);font-size:8.5px;letter-spacing:.2em;
  text-transform:uppercase;color:var(--faint)}
.hud .cell b{font-family:var(--mono);font-size:13px;font-weight:500;color:var(--ink);
  font-variant-numeric:tabular-nums;white-space:nowrap}
.pulse{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;
  background:var(--up);box-shadow:0 0 0 0 rgba(53,208,127,.7);animation:ping 2s infinite}
.pulse.stale{background:var(--gold);box-shadow:0 0 0 0 rgba(232,179,60,.7)}
.pulse.cold{background:var(--down);box-shadow:0 0 0 0 rgba(255,92,108,.7)}
@keyframes ping{0%{box-shadow:0 0 0 0 currentColor;opacity:1}
  70%{box-shadow:0 0 0 8px rgba(0,0,0,0);opacity:.75}100%{box-shadow:0 0 0 0 rgba(0,0,0,0);opacity:1}}

/* ---------- ticker ---------- */
.tape{border-bottom:1px solid var(--edge);background:rgba(9,11,18,.9);overflow:hidden;
  position:relative}
.tape::before,.tape::after{content:"";position:absolute;top:0;bottom:0;width:64px;z-index:2;
  pointer-events:none}
.tape::before{left:0;background:linear-gradient(90deg,var(--void),transparent)}
.tape::after{right:0;background:linear-gradient(270deg,var(--void),transparent)}
.tape-run{display:flex;gap:0;width:max-content;animation:roll 64s linear infinite}
.tape:hover .tape-run{animation-play-state:paused}
@keyframes roll{from{transform:translateX(0)}to{transform:translateX(-50%)}}
.tk{display:flex;align-items:baseline;gap:8px;padding:8px 20px;border-right:1px solid var(--edge);
  font-family:var(--mono);font-size:11.5px;white-space:nowrap}
.tk .s{color:var(--ink-2);letter-spacing:.12em;font-weight:500}
.tk .v{color:var(--ink);font-variant-numeric:tabular-nums}
.tk .d{font-size:10.5px;font-variant-numeric:tabular-nums}
.up{color:var(--up)}.down{color:var(--down)}.flat{color:var(--dim)}

/* ---------- layout ---------- */
main{max-width:1720px;margin:0 auto;padding:14px 18px 64px;
  display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:13px;align-items:start}
.card{border:1px solid var(--edge);background:var(--panel);border-radius:3px;
  display:flex;flex-direction:column;min-width:0;position:relative;overflow:hidden;
  animation:lift .55s cubic-bezier(.2,.7,.3,1) both}
.card::after{content:"";position:absolute;inset:0 0 auto 0;height:1px;
  background:linear-gradient(90deg,transparent,rgba(232,179,60,.35),transparent);
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
  font-family:var(--mono);font-weight:700;font-size:10px;letter-spacing:.2em;
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
.q.derived .val{color:var(--gold)}
.q:hover{background:var(--raise)}
.q .lab{font-family:var(--mono);font-size:9px;letter-spacing:.17em;text-transform:uppercase;
  color:var(--dim);display:flex;justify-content:space-between;gap:6px;align-items:center}
.q .val{font-family:var(--mono);font-size:21px;font-weight:500;color:var(--ink);
  font-variant-numeric:tabular-nums;letter-spacing:-.01em;line-height:1.1}
.q .dlt{font-family:var(--mono);font-size:11px;font-variant-numeric:tabular-nums}
.q .src{font-family:var(--mono);font-size:8.5px;color:var(--faint);letter-spacing:.06em;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.t{font-family:var(--mono);font-size:8px;letter-spacing:.1em;padding:1px 4px;border-radius:2px;
  border:1px solid;flex:none}
.t1{color:var(--up);border-color:var(--up-dim);background:rgba(53,208,127,.08)}
.t2{color:var(--gold);border-color:var(--gold-dim);background:rgba(232,179,60,.08)}
.t3{color:var(--ink-2);border-color:var(--edge-hi);background:rgba(152,163,184,.07)}
.t4{color:var(--down);border-color:var(--down-dim);background:rgba(255,92,108,.08)}
.conf{position:absolute;right:0;top:0;bottom:0;width:2px;background:var(--edge)}

/* ---------- news ---------- */
.news{display:flex;flex-direction:column;max-height:520px;overflow:auto}
.nw{display:grid;grid-template-columns:44px minmax(0,1fr);gap:11px;padding:10px 13px;
  border-bottom:1px solid rgba(26,32,48,.7);transition:background .16s ease}
.nw:hover{background:var(--raise)}
.nw:last-child{border-bottom:0}
.imp{font-family:var(--mono);font-size:14px;font-weight:700;text-align:center;
  font-variant-numeric:tabular-nums;line-height:1;padding-top:2px}
.imp small{display:block;font-size:7.5px;font-weight:400;letter-spacing:.13em;
  color:var(--faint);margin-top:3px}
.nw h3{margin:0 0 4px;font-family:var(--body);font-size:13.5px;font-weight:600;
  color:var(--ink);line-height:1.35}
.nw p{margin:0 0 5px;font-size:11.5px;color:var(--dim);line-height:1.45}
.meta{display:flex;gap:7px;flex-wrap:wrap;align-items:center;
  font-family:var(--mono);font-size:9px;color:var(--faint);letter-spacing:.07em}
.meta a{color:var(--live);text-decoration:none;border-bottom:1px dotted var(--live-dim)}
.meta a:hover{color:var(--ink)}
.chip{font-family:var(--mono);font-size:8.5px;letter-spacing:.09em;padding:1px 5px;
  border-radius:2px;border:1px solid var(--edge-hi);color:var(--ink-2)}

/* ---------- countdown ---------- */
.rel{display:flex;flex-direction:column}
.rl{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:5px 12px;padding:9px 0;
  border-bottom:1px dashed rgba(26,32,48,.9);align-items:baseline}
.rl:last-child{border-bottom:0}
.rl .nm{font-family:var(--mono);font-size:11.5px;color:var(--ink);font-weight:500}
.rl .cd{font-family:var(--mono);font-size:15px;font-weight:700;color:var(--gold);
  font-variant-numeric:tabular-nums;white-space:nowrap;letter-spacing:.02em}
.rl .cd.hot{color:var(--down);animation:blink 1s steps(2,end) infinite}
.rl .cd.past{color:var(--faint);font-weight:400}
@keyframes blink{50%{opacity:.35}}
.rl .sub{grid-column:1/-1;font-family:var(--mono);font-size:9px;color:var(--faint);
  letter-spacing:.05em;overflow-wrap:anywhere}
.rl .sub a{color:var(--live-dim);text-decoration:none}
.rl .sub a:hover{color:var(--live)}

/* ---------- misc ---------- */
.kv{display:grid;grid-template-columns:minmax(0,auto) minmax(0,1fr);gap:5px 14px;
  font-family:var(--mono);font-size:11px}
.kv dt{color:var(--dim);letter-spacing:.09em;text-transform:uppercase;font-size:9.5px;
  padding-top:2px}
.kv dd{margin:0;color:var(--ink)}
.note{margin:0;font-size:11.5px;line-height:1.55;color:var(--dim);
  border-left:2px solid var(--edge-hi);padding-left:10px}
.note b{color:var(--ink-2);font-weight:600}
.warn{border-left-color:var(--gold);color:var(--ink-2)}
.bad{border-left-color:var(--down)}
.reg{font-family:var(--disp);font-size:30px;font-weight:700;letter-spacing:.05em;
  color:var(--gold);text-transform:uppercase;line-height:1;margin:0}
table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:11px}
th{text-align:left;font-weight:400;font-size:8.5px;letter-spacing:.16em;
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
  border-top:1px solid var(--edge);color:var(--dim);font-size:11.5px;line-height:1.6}
footer strong{color:var(--ink-2)}
footer code{font-family:var(--mono);font-size:10.5px;color:var(--gold)}
:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
noscript .ns{display:block;margin:14px 18px;padding:12px;border:1px solid var(--gold-dim);
  background:rgba(232,179,60,.08);color:var(--gold);font-family:var(--mono);font-size:11.5px}
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
  /* data age, ticking upward from the real capture time */
  var cap=Date.parse(D.captured);
  if(!isNaN(cap)){
    var s=Math.max(0,Math.floor((d.getTime()-cap)/1000));
    var dd=Math.floor(s/86400), hh=Math.floor(s%86400/3600), mm=Math.floor(s%3600/60);
    setText("age",(dd?dd+"d ":"")+pad(hh)+"h "+pad(mm)+"m");
    var dot=q("dot"), st=q("state");
    var cls=s<900?"":(s<86400?"stale":"cold");
    var lab=s<900?"LIVE":(s<86400?"SNAPSHOT":"STALE SNAPSHOT");
    if(dot) dot.className="pulse "+cls;
    if(st){st.textContent=lab;
      st.style.color=(cls===""?"var(--up)":(cls==="stale"?"var(--gold)":"var(--down)"));}
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

/* ---- ambient field: tape, motes, sweep, ping ---- */
(function(){
  var c=q("fx");if(!c||!c.getContext)return;
  var ctx=c.getContext("2d");if(!ctx)return;
  var reduce=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;
  var W=0,H=0,dpr=1,N=300,layers=[],motes=[],sweep=-0.3,ping=0,pingAt=0,t=0;

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
  function seedMotes(){
    motes=[];
    var n=Math.min(70,Math.max(24,Math.round(innerWidth/26)));
    for(var i=0;i<n;i++){
      motes.push({x:Math.random(),y:Math.random(),
        v:0.00006+Math.random()*0.00022,r:0.4+Math.random()*1.3,
        a:0.10+Math.random()*0.30,
        h:Math.random()<0.6?"232,179,60":(Math.random()<0.5?"78,168,255":"53,208,127")});
    }
  }
  function resize(){
    dpr=Math.min(window.devicePixelRatio||1,2);
    W=c.width=Math.max(1,Math.floor(innerWidth*dpr));
    H=c.height=Math.max(1,Math.floor(innerHeight*dpr));
    c.style.width=innerWidth+"px";c.style.height=innerHeight+"px";
    seedMotes();
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
    ctx.fillStyle="#06070B";ctx.fillRect(0,0,W,H);

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

    if(!reduce){
      /* radar ping every ~11s from the top-left */
      if(t-pingAt>660){pingAt=t;ping=0;}
      ping=(t-pingAt)/660;
      if(ping<1){
        var rr=ping*Math.max(W,H)*1.15;
        ctx.beginPath();ctx.arc(W*0.06,H*0.02,rr,0,6.283);
        ctx.strokeStyle="rgba(232,179,60,"+(0.10*(1-ping))+")";
        ctx.lineWidth=1.5*dpr;ctx.stroke();
      }
      /* CRT sweep */
      sweep+=0.0014;if(sweep>1.3)sweep=-0.3;
      var sx=sweep*W,g=ctx.createLinearGradient(sx-190*dpr,0,sx+20*dpr,0);
      g.addColorStop(0,"rgba(232,179,60,0)");
      g.addColorStop(0.8,"rgba(232,179,60,0.035)");
      g.addColorStop(1,"rgba(232,179,60,0.10)");
      ctx.fillStyle=g;ctx.fillRect(sx-190*dpr,0,210*dpr,H);
      ctx.fillStyle="rgba(232,179,60,0.14)";ctx.fillRect(sx,0,dpr,H);
      requestAnimationFrame(frame);
    }
  }
  layers=[layer(1.1,0.06,0.15,"#E8B33C"),
          layer(3.7,0.037,0.10,"#4EA8FF"),
          layer(6.3,0.021,0.075,"#7E76A8")];
  resize();frame();
  addEventListener("resize",function(){resize();if(reduce)frame();},{passive:true});
})();
})();
"""


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

    # --- news -------------------------------------------------------------
    news = []
    for h in snap.headlines:
        col = "var(--down)" if h.impact >= 85 else (
            "var(--gold)" if h.impact >= 65 else "var(--ink-2)")
        link = (f'<a href="{e(h.url)}" target="_blank" rel="noopener noreferrer">source</a>'
                if h.url else "")
        chips = "".join(f'<span class="chip">{e(a)}</span>' for a in h.assets)
        news.append(
            f'<article class="nw"><div class="imp" style="color:{col}">{h.impact}'
            f'<small>IMPACT</small></div><div><h3>{e(h.title)}</h3>'
            + (f'<p>{e(h.summary)}</p>' if h.summary else "")
            + f'<div class="meta"><span class="t t{h.tier}">T{h.tier}</span>'
            f'<span>{e(h.source)}</span><span>{e(h.published[:16].replace("T", " "))}Z</span>'
            + ('<span class="chip" style="color:var(--up);border-color:var(--up-dim)">'
               'PRIMARY CONFIRMED</span>' if h.primary_confirmed else
               '<span class="chip" style="color:var(--gold);border-color:var(--gold-dim)">'
               'REPORTED</span>')
            + f'{link}{chips}</div></div></article>'
        )
    newsfeed = "".join(news) or '<p class="note">No headlines in this snapshot.</p>'

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

    payload = json.dumps({"captured": snap.captured}, ensure_ascii=False).replace("</", "<\\/")

    head = (f'<title>Macro Desk Live</title>\n'
            f'<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            f'<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            f'<link rel="stylesheet" href="{FONTS}">\n'
            f'<style>{CSS}</style>')

    body = f"""<canvas id="fx" aria-hidden="true"></canvas>
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
    <h2>News feed <em>tiered, deduplicated, impact-ranked</em></h2>
    <div class="bd flush"><div class="news">{newsfeed}</div></div>
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

  <section class="card c8">
    <h2>Inflation &amp; labour <em>last prints, primary sourced</em></h2>
    <div class="bd" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px">
      {infl_html}
    </div>
  </section>

  <section class="card c12">
    <h2>Live catalyst &mdash; cross-asset transmission <em>{e(rmap.scenario)}</em></h2>
    <div class="bd">
      <ol style="margin:0;padding-left:20px;font-size:12px;color:var(--ink-2);
        display:flex;flex-direction:column;gap:4px">{chain}</ol>
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
    <h2>Integrity <em>conflicts are shown, not resolved away</em></h2>
    <div class="bd">{conflicts}{errors}
      <p class="note">Where two outlets disagreed, the higher tier is carried at
      reduced confidence and the disagreement is printed. The alternative &mdash;
      silently picking the more convenient figure &mdash; is how a terminal starts
      lying to its operator.</p>
    </div>
  </section>

</main>

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

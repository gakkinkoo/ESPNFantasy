#!/usr/bin/env python3
"""Fantasy Basketball dashboard (ESPN league). Roster, positions, injuries, ranks and projections
come from ESPN; schedule and real stats come from the NBA.
Install (once):  pip install nba_api scipy numpy pandas
Run:             double-click fantasy.py -> creates index.html and opens it in the browser
Keep espn_fantasy_basketball.png in the same folder (header logo).
"""
import os, json, base64, unicodedata, urllib.request, urllib.error, webbrowser, traceback
import datetime as dt
from zoneinfo import ZoneInfo
import numpy as np
from scipy.optimize import linear_sum_assignment
from nba_api.stats.endpoints import leaguedashplayerstats as lds

SEASON = "2026-27"
ESPN_YEAR = 2027
DAYS = 7
FA_LIMIT = 150          # how many free agents to load (sorted by % owned)
LEAGUE_ID = os.environ.get("LEAGUE_ID", "304996223")
MY_TEAM = os.environ.get("MY_TEAM", "Kebabaren")   # part of your team name in the league
ESPN_S2 = os.environ.get("ESPN_S2", "")            # only needed if the league is private (cookie espn_s2)
SWID = os.environ.get("SWID", "")               # only needed if the league is private (cookie SWID, with {braces})

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "index.html")
BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/%d/segments/0/leagues/%s" % (ESPN_YEAR, LEAGUE_ID)
POSES = ["PG", "SG", "SF", "PF", "C"]
PCOL = {"PG": "#4d8cf5", "SG": "#22c3c3", "SF": "#2ecc71", "PF": "#ffb43c", "C": "#ff5c7a"}
DEFPOS = {1: "PG", 2: "SG", 3: "SF", 4: "PF", 5: "C"}
SLOT_NAME = {0: "PG", 1: "SG", 2: "SF", 3: "PF", 4: "C", 5: "G", 6: "F", 11: "UTIL", 12: "BE", 13: "IR"}
PRO = {1: "ATL", 2: "BOS", 3: "NOP", 4: "CHI", 5: "CLE", 6: "DAL", 7: "DEN", 8: "DET", 9: "GSW", 10: "HOU",
       11: "IND", 12: "LAC", 13: "LAL", 14: "MIA", 15: "MIL", 16: "MIN", 17: "BKN", 18: "NYK", 19: "ORL",
       20: "PHI", 21: "PHX", 22: "POR", 23: "SAC", 24: "SAS", 25: "OKC", 26: "UTA", 27: "WAS", 28: "TOR",
       29: "MEM", 30: "CHA"}
SLOTS = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL", "UTIL", "UTIL"]
ELIG = {"G": {"PG", "SG"}, "F": {"SF", "PF"}, "UTIL": None}
CARD_KEYS = ("rank", "avg", "tot", "ptot", "pavg", "inj", "l7", "l15", "gp", "pg")
COLS = [("POS RANK", "gE"), ("AVG FPTS", "gE"), ("2027 FPTS", "gE"), ("2027 PROJ", "gE"), ("FP L15", "gF"),
        ("FP L7", "gF")] + [(c, "gS") for c in ("GP", "MIN", "PTS", "REB", "AST", "STL", "BLK", "TO", "3PM", "FG%")]
LEGEND = [
    ("POS RANK", "Rank among players at his position (ESPN, this season)"),
    ("AVG FPTS", "Average fantasy points per game (your league's scoring)"),
    ("2027 FPTS", "Total fantasy points this season so far"),
    ("2027 PROJ", "ESPN projected fantasy points for the season (and per game)"),
    ("FP L15 / L7", "Average fantasy points over the last 15 / 7 games"),
    ("GP", "Games played"), ("MIN", "Minutes per game"), ("PTS / REB / AST", "Points, rebounds, assists per game"),
    ("STL / BLK", "Steals, blocks per game"), ("TO", "Turnovers per game"), ("3PM", "Three-pointers made per game"),
    ("FG%", "Field goal percentage"), ("Games", "Games in the next 7 days"),
    ("vs / @", "Home game / away game"),
    ("PG SG SF PF C", "Point guard, shooting guard, small forward, power forward, center"),
    ("G / F / UTIL", "Guard slot (PG/SG), forward slot (SF/PF), any position"),
    ("BE / IR / FA", "Bench, injured reserve, free agent"), ("OUT / DTD", "Out / day-to-day"),
    ("Tip", "Click any column header to sort the table by it."),
]

CSS = """
:root{--bg:#0b0e14;--card:#151922;--line:#2b3345;--blue:#4d8cf5;--red:#e0001b;--gold:#ffb43c;
--green:#2ecc71;--purple:#a07bff;--teal:#22c3c3;--text:#eef1f7;--muted:#8d97ad}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1200px 500px at 10% -10%,#16213a 0,var(--bg) 60%);color:var(--text);
font-family:Inter,"Segoe UI",system-ui,sans-serif;font-size:14px}
header{display:flex;align-items:center;gap:16px;padding:10px 20px;background:linear-gradient(90deg,#000,#10131b);border-bottom:3px solid var(--red)}
header img{height:64px}
header b{font-family:"Barlow Condensed",Inter,sans-serif;font-size:30px;letter-spacing:.5px;display:block;line-height:1}
header .t{color:var(--gold);font-weight:600}
.ctl{position:sticky;top:0;z-index:5;display:flex;align-items:center;gap:12px;padding:8px 20px;background:#0d1119f2;border-bottom:1px solid var(--line)}
.ctl label{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:1px}
select{background:var(--card);color:#fff;border:1px solid var(--line);border-radius:8px;padding:7px 12px;font-size:14px}
main{padding:6px 20px}
h2{font-family:"Barlow Condensed",Inter,sans-serif;font-size:22px;letter-spacing:1px;text-transform:uppercase;margin:26px 0 10px;
border-left:5px solid var(--red);padding-left:10px}
.split{display:grid;grid-template-columns:minmax(0,1fr) 250px;gap:14px;align-items:start}
@media(max-width:1100px){.split{grid-template-columns:1fr}}
.w{overflow-x:auto;background:var(--card);border-radius:12px;border:1px solid var(--line);box-shadow:0 4px 18px #0006}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid var(--line);padding:6px 9px;text-align:center;white-space:nowrap}
th{background:#10141c;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.5px}
th[data-i]{cursor:pointer}th[data-i]:hover{color:#fff}
th[data-dir=desc]::after{content:' ▼';color:var(--gold)}th[data-dir=asc]::after{content:' ▲';color:var(--gold)}
tbody tr:nth-child(even) td{background:#181d28}
tbody tr:hover td{background:#202738}
th.gE{background:#3a1119;color:#ff8d9b}th.gF{background:#2a2147;color:#c3b0ff}
th.gS{background:#12304f;color:#8cc0ff}th.gD{background:#0f3a3a;color:#7fe3e3}
.today{color:var(--gold)}
td.pl{text-align:left;display:flex;align-items:center;gap:10px;min-width:210px}
td.pl div{line-height:1.25}
.ph{width:44px;height:34px;border-radius:50%;object-fit:cover;object-position:top;background:#252b3a;flex:none}
td.ln{text-align:left;min-width:130px}
td.ln .ph{float:left;margin-right:8px}
.opp{font-size:11px;font-weight:700;padding:1px 6px;border-radius:3px}
.hm{background:#12402a;color:var(--green)}.aw{background:#40250f;color:var(--gold)}
.g{color:var(--teal);font-size:12px;font-weight:600}
.key{color:var(--blue);font-weight:700}
.up{color:var(--green);font-weight:700}.dn{color:#ff6b7d;font-weight:700}
.out{background:var(--red);padding:1px 6px;border-radius:3px;font-size:11px;font-weight:700}
.dtd{background:var(--gold);color:#000;padding:1px 6px;border-radius:3px;font-size:11px;font-weight:700}
.sl{background:#1d3a6b;color:#9cc2ff;padding:2px 8px;border-radius:4px;font-weight:700;font-size:12px}
.be{background:#33384a;color:#c4cadb;padding:2px 8px;border-radius:4px;font-weight:700;font-size:12px}
.ir{background:#3b2a6b;color:#c3b0ff;padding:2px 8px;border-radius:4px;font-weight:700;font-size:12px}
small,.m{color:var(--muted)}
.bar{display:flex;height:18px;width:280px;background:#10141c;border-radius:4px;overflow:hidden}
.bar i{display:block;height:100%}
.legend{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.legend h4{margin:0 0 6px;font-family:"Barlow Condensed",Inter,sans-serif;font-size:20px;letter-spacing:1px;color:var(--gold)}
.legend dt{font-weight:700;color:var(--blue);margin-top:8px;font-size:12px}
.legend dd{margin:0;color:var(--muted);font-size:12px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:14px}
.rc{background:var(--card);border:1px solid var(--line);border-top:4px solid var(--c);border-radius:12px;padding:10px 14px;box-shadow:0 4px 18px #0006}
.rc h3{margin:2px 0 8px;font-family:"Barlow Condensed",Inter,sans-serif;font-size:20px;letter-spacing:.8px;text-transform:uppercase;color:var(--c)}
.ri{display:flex;align-items:center;gap:10px;padding:7px 0;border-top:1px solid var(--line)}
.ri small{display:block}
footer{color:var(--muted);font-size:11px;padding:6px 20px 20px}
.w{-webkit-overflow-scrolling:touch}
.cmpbar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px}
#cmpout td:first-child,#cmpout th:first-child{text-align:left}
#cmpout th{font-size:12px;text-transform:none;color:var(--text)}
td.best{background:#12402a!important;color:var(--green);font-weight:700}
input{background:var(--card);color:#fff;border:1px solid var(--line);border-radius:8px;padding:7px 12px;font-size:14px;min-width:220px}
@media(max-width:700px){header{padding:8px 12px}header img{height:46px}header b{font-size:22px}
.ctl{padding:8px 12px;flex-wrap:wrap}main{padding:6px 10px}h2{font-size:19px}select,input{font-size:16px;max-width:100%}
td.pl{min-width:175px}th,td{padding:5px 7px}.bar{width:150px}}
"""
JS = """
function show(i){document.querySelectorAll('.v').forEach(function(e){e.style.display=e.classList.contains('v'+i)?'block':'none'})}
document.addEventListener('click',function(ev){
 var th=ev.target.closest('th[data-i]');if(!th)return;
 var tb=th.closest('table'),i=+th.dataset.i,body=tb.tBodies[0],asc=th.dataset.dir==='desc';
 tb.querySelectorAll('th[data-dir]').forEach(function(x){x.removeAttribute('data-dir')});
 th.dataset.dir=asc?'asc':'desc';
 function key(r){var c=r.cells[i],v=c.dataset.v!==undefined?c.dataset.v:c.textContent.trim();
  if(v===''||v==='–')return null;var n=parseFloat(v.replace(/[^0-9.\\-]/g,''));return isNaN(n)?v.toLowerCase():n}
 var rows=[].slice.call(body.rows);
 rows.sort(function(a,b){var x=key(a),y=key(b);if(x===null&&y===null)return 0;if(x===null)return 1;if(y===null)return -1;
  var r=(typeof x==='number'&&typeof y==='number')?x-y:String(x).localeCompare(String(y));return asc?r:-r});
 rows.forEach(function(r){body.appendChild(r)});
});
var CM='teams';
function esc(t){return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function cmode(m){CM=m;fill()}
var LAB={};
function nz(t){return String(t).normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().trim()}
function lab(x){return x.name+(CM==='players'&&x.sub?' ('+x.sub+')':'')}
function fill(){var L=CM==='teams'?DATA.teams:DATA.players;LAB={};
 var dl=document.getElementById('dl');dl.innerHTML='';
 L.forEach(function(x){var t=lab(x);LAB[t]=x;var o=document.createElement('option');o.value=t;dl.appendChild(o)});
 ['ca','cb','cc','cd','ce'].forEach(function(id,k){document.getElementById(id).value=(k<2&&L[k])?lab(L[k]):''});cmp()}
function pick(v){v=nz(v);if(!v)return null;
 for(var t in LAB){if(nz(t)===v)return LAB[t]}
 for(var t in LAB){if(nz(t).indexOf(v)>=0)return LAB[t]}return null}
function cmp(){var M=CM==='teams'?DATA.tm:DATA.pm;
 var sel=['ca','cb','cc','cd','ce'].map(function(id){return pick(document.getElementById(id).value)}).filter(Boolean);
 var h='<table><thead><tr><th>Metric</th>';
 sel.forEach(function(x){h+='<th>'+(x.img?'<img class="ph" src="https://a.espncdn.com/i/headshots/nba/players/full/'+x.img+'.png" onerror="this.remove()"> ':'')+esc(x.name)+'</th>'});
 h+='</tr></thead><tbody>';
 M.forEach(function(m){var vals=sel.map(function(x){return x.v[m[0]]}),best=null;
  if(m[2]!==0){var nums=vals.filter(function(v){return v!==null&&v!==undefined});
   if(nums.length>1)best=m[2]>0?Math.max.apply(null,nums):Math.min.apply(null,nums)}
  h+='<tr><td>'+m[1]+'</td>';
  vals.forEach(function(v){var t=(v===null||v===undefined)?'–':Number(v).toFixed(m[3]);
   h+='<td'+(best!==null&&v===best?' class="best"':'')+'>'+t+'</td>'});h+='</tr>'});
 document.getElementById('cmpout').innerHTML=h+'</tbody></table>'}
var T0=Date.now();
document.addEventListener('visibilitychange',function(){
 if(!document.hidden&&Date.now()-T0>600000){location.replace(location.pathname+'?t='+Date.now())}});
"""
CTX = {}


def logo_html():
    f = os.path.join(HERE, "espn_fantasy_basketball.png")
    if os.path.exists(f):
        with open(f, "rb") as fh:
            return "<img alt='ESPN Fantasy' src='data:image/png;base64,%s'>" % base64.b64encode(fh.read()).decode()
    return "<b>ESPN Fantasy</b>"


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return "".join(c for c in s if c.isalnum())


def get_json(url, headers=None):
    h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json"}
    h.update(headers or {})
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30))


def espn_hdr(extra=None):
    h = dict(extra or {})
    if ESPN_S2:
        h["Cookie"] = "espn_s2=%s; SWID=%s" % (ESPN_S2, SWID)
    return h


def n(v, fmt="%.1f"):
    return "–" if v is None else fmt % v


def td(v, cls="", dv=None):
    return "<td%s%s>%s</td>" % (" class='%s'" % cls if cls else "", " data-v='%s'" % dv if dv is not None else "", v)


def photo(pid):
    return ("<img class='ph' loading='lazy' src='https://a.espncdn.com/i/headshots/nba/players/full/%s.png' "
            "onerror=\"this.style.visibility='hidden'\">" % pid)


def slot_badge(slot):
    nm = "FA" if slot is None else SLOT_NAME.get(slot, "?")
    return "<span class='%s'>%s</span>" % ("be" if nm in ("BE", "FA") else "ir" if nm == "IR" else "sl", nm)


def short_status(s):
    s = (s or "").upper()
    return "OUT" if ("OUT" in s or "RESERVE" in s) else "DTD" if "DAY" in s else ""


STAT_IDS = {"MIN": "40", "PTS": "0", "REB": "6", "AST": "3", "STL": "2", "BLK": "1", "TO": "11", "3PM": "17"}


def parse_card(e):
    """ESPN player entry (roster entry, player card or free-agent row) -> rank, fantasy points, per-game stats."""
    p, Y = e.get("player") or {}, ESPN_YEAR
    sts = p.get("stats") or []
    by_id = {x.get("id"): x for x in sts}
    by_src = {(x.get("statSourceId"), x.get("statSplitTypeId")): x for x in sts if x.get("seasonId") == Y}
    get = lambda i, k: by_id.get("%s%d" % (i, Y)) or by_src.get(k) or {}
    act, prj, l7, l15 = get("00", (0, 0)), get("10", (1, 0)), get("01", (0, 1)), get("02", (0, 2))
    tot, avg = act.get("stats") or {}, act.get("averageStats") or {}
    gp = tot.get("42")

    def per(i):
        v = avg.get(i)
        if v is None and tot.get(i) is not None and gp:
            v = tot[i] / gp
        return v
    pg = {k: per(i) for k, i in STAT_IDS.items()}
    pg["FG"] = 100.0 * tot["13"] / tot["14"] if tot.get("13") is not None and tot.get("14") else None
    rts = e.get("ratings") or p.get("ratings") or {}     # ratings sit next to "player", not inside it
    rt = rts.get("0") or next(iter(rts.values()), {})
    return dict(rank=rt.get("positionalRanking"), avg=act.get("appliedAverage"), tot=act.get("appliedTotal"),
                ptot=prj.get("appliedTotal"), pavg=prj.get("appliedAverage"), inj=p.get("injuryStatus"),
                l7=l7.get("appliedAverage"), l15=l15.get("appliedAverage"), gp=gp, pg=pg)


def merge_cards(a, b):
    out = {}
    for key in CARD_KEYS:
        x, y = (a or {}).get(key), (b or {}).get(key)
        out[key] = ({k: (x.get(k) if x.get(k) is not None else (y or {}).get(k)) for k in set(x) | set(y or {})}
                    if isinstance(x, dict) else (x if x is not None else y))
    return out


def parse_entry(p, slot, card):
    elig = [POSES[s] for s in p.get("eligibleSlots", []) if s in range(5)]
    prim = DEFPOS.get(p.get("defaultPositionId"))
    return dict(id=p["id"], name=p["fullName"], slot=slot, elig=elig or [prim or "?"], primary=prim,
                team=PRO.get(p.get("proTeamId"), "?"), inj=p.get("injuryStatus"), card=card)


def fetch_league():
    try:
        data = get_json(BASE + "?view=mTeam&view=mRoster", espn_hdr())
    except urllib.error.HTTPError as e:
        raise RuntimeError("ESPN returned HTTP %s. If the league is private, fill in ESPN_S2 and SWID "
                           "at the top of the script." % e.code)
    teams = []
    for t in data.get("teams", []):
        name = t.get("name") or ("%s %s" % (t.get("location", ""), t.get("nickname", ""))).strip()
        entries = [parse_entry(en["playerPoolEntry"]["player"], en.get("lineupSlotId"), parse_card(en["playerPoolEntry"]))
                   for en in t.get("roster", {}).get("entries", [])]
        teams.append(dict(id=t["id"], name=name, owners=t.get("owners", []), entries=entries))
    return teams, data.get("scoringPeriodId")


def card_filter(sp, **extra):
    Y = ESPN_YEAR
    f = {"filterStatsForTopScoringPeriodIds": {"value": 5, "additionalValue": ["00%d" % Y, "10%d" % Y, "01%d" % Y, "02%d" % Y]},
         "filterRanksForScoringPeriodIds": {"value": [sp] if sp else []},
         "filterRanksForRankTypes": {"value": ["STANDARD"]}}
    f.update(extra)
    return json.dumps({"players": f})


def debug_dump(name, obj):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1)


def fetch_cards(ids, sp):
    out = {}
    try:
        flt = card_filter(sp, filterIds={"value": ids}, limit=len(ids) + 10)
        data = get_json(BASE + "?view=kona_playercard", espn_hdr({"x-fantasy-filter": flt}))
        for e in data.get("players", []):
            out[e.get("id") or (e.get("player") or {}).get("id")] = parse_card(e)
        print("ESPN player cards: %d players, %d with fantasy points, %d with POS rank" % (
            len(out), sum(c["avg"] is not None for c in out.values()), sum(c["rank"] is not None for c in out.values())))
        if not any(c["avg"] is not None for c in out.values()):
            debug_dump("espn_debug.json", data.get("players", [])[:2])
            print("No fantasy points found - saved espn_debug.json (send it to Claude).")
        if not any((c.get("pg") or {}).get("PTS") is not None for c in out.values()) and data.get("players"):
            dbg = [x for x in ((data["players"][0].get("player") or {}).get("stats") or []) if x.get("seasonId") == ESPN_YEAR][:3]
            debug_dump("espn_stats_debug.json", dbg)
            print("No per-game stats found. Send this to Claude:", json.dumps(dbg)[:2500])
    except Exception as ex:
        print("ESPN player cards failed:", ex)
    return out


def fetch_free_agents(sp):
    out = []
    try:
        flt = card_filter(sp, filterStatus={"value": ["FREEAGENT", "WAIVERS"]}, limit=FA_LIMIT, offset=0,
                          sortPercOwned={"sortPriority": 1, "sortAsc": False})
        data = get_json(BASE + "?view=kona_player_info", espn_hdr({"x-fantasy-filter": flt}))
        out = [parse_entry(e["player"], None, parse_card(e)) for e in data.get("players", [])]
        print("Free agents loaded:", len(out))
    except Exception as ex:
        print("Free agents failed:", ex)
    return out


def fetch_injuries():
    out = {}
    try:
        d = get_json("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries")
        for t in d.get("injuries", []):
            for i in t.get("injuries", []):
                out[norm((i.get("athlete") or {}).get("displayName"))] = dict(
                    status=i.get("status", ""), ret=((i.get("details") or {}).get("returnDate") or "")[:10])
    except Exception as ex:
        print("Injury report failed:", ex)
    return out


def fetch_stats(k):
    df = lds.LeagueDashPlayerStats(season=SEASON, per_mode_detailed="Totals",
                                   last_n_games=k, timeout=25).get_data_frames()[0]
    return {norm(r["PLAYER_NAME"]): r for r in df.to_dict("records")}


def fantasy(r):
    gp = r["GP"]
    if not gp:
        return None
    t = (r["PTS"] + r["REB"] + 2 * r["AST"] + 4 * r["STL"] + 4 * r["BLK"] - 2 * r["TOV"]
         - 0.5 * r["PF"] + 0.5 * r["FG3M"] - 0.3 * (r["FG3A"] - r["FG3M"])
         - 0.3 * (r["FGA"] - r["FGM"]) + 0.3 * r["FTM"] - 0.6 * (r["FTA"] - r["FTM"])
         + 4 * r["DD2"] + 6 * r["TD3"])
    return t / gp


def fetch_schedule():
    hdr = {"Referer": "https://www.nba.com/", "Origin": "https://www.nba.com"}
    base = "https://cdn.nba.com/static/json/staticData/"
    for name in ("scheduleLeagueV2.json", "scheduleLeagueV2_1.json"):
        try:
            sched = {}
            for gd in get_json(base + name, hdr)["leagueSchedule"]["gameDates"]:
                for g in gd["games"]:
                    d = g["gameDateEst"][:10]
                    h, a = g["homeTeam"]["teamTricode"], g["awayTeam"]["teamTricode"]
                    if h and a:
                        sched.setdefault(d, {})[h] = "vs " + a
                        sched.setdefault(d, {})[a] = "@" + h
            return sched
        except Exception as e:
            print("Schedule failed:", name, e)
    return {}


def fetch_schedule_espn(days):
    fix = {"NY": "NYK", "GS": "GSW", "SA": "SAS", "NO": "NOP", "UTAH": "UTA", "WSH": "WAS"}
    sched = {}
    for d in days:
        try:
            data = get_json("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=" + d.replace("-", ""))
            for ev in data.get("events", []):
                comp = ev["competitions"][0]["competitors"]
                h = next(c for c in comp if c["homeAway"] == "home")["team"]["abbreviation"]
                a = next(c for c in comp if c["homeAway"] == "away")["team"]["abbreviation"]
                h, a = fix.get(h, h), fix.get(a, a)
                sched.setdefault(d, {})[h] = "vs " + a
                sched.setdefault(d, {})[a] = "@" + h
        except Exception as ex:
            print("ESPN schedule failed for", d, ex)
    return sched


def best_lineup(players, day):
    sched = CTX["sched"]
    act = [p for p in players if p["status"] != "OUT" and p["slot"] != 13]
    M = np.full((len(act), len(SLOTS)), -1e6)
    for i, p in enumerate(act):
        if p["team"] in sched.get(day, {}):
            for j, s in enumerate(SLOTS):
                el = ELIG.get(s, {s})
                if el is None or set(p["elig"]) & el:
                    M[i, j] = max(p["val"], 0.01)
    res = [None] * len(SLOTS)
    if len(act):
        for i, j in zip(*linear_sum_assignment(M, maximize=True)):
            if M[i, j] > 0:
                res[j] = (act[i], sched[day][act[i]["team"]])
    return res


def day_header():
    return "".join("<th class='%s'>%s</th>" % ("today" if i == 0 else "", d.strftime("%a<br>%b %d"))
                   for i, d in enumerate(CTX["dates"]))


def roster_table(players):
    sched, days = CTX["sched"], CTX["days"]
    gi = 2 + len(COLS) + DAYS
    head = ("<tr><th rowspan='2' data-i='0'>Player</th><th rowspan='2' data-i='1'>Slot</th><th colspan='4' class='gE'>ESPN</th>"
            "<th colspan='2' class='gF'>Form</th><th colspan='10' class='gS'>Per game (NBA)</th>"
            "<th colspan='%d' class='gD'>Next %d days</th><th rowspan='2' data-i='%d'>Games</th></tr><tr>%s%s</tr>" % (
                DAYS, DAYS, gi, "".join("<th class='%s' data-i='%d'>%s</th>" % (g, i + 2, c) for i, (c, g) in enumerate(COLS)),
                day_header()))
    rows = []
    for p in sorted(players, key=lambda p: -(p["avg"] or 0)):
        s, c = p["st"], p["c"]
        tag = ""
        if p["status"]:
            tag = " <span class='%s'>%s</span><br><small>Return: %s</small>" % (
                "out" if p["status"] == "OUT" else "dtd", p["status"], p["ret"] or "unknown")
        if not p["gp"]:
            tag += "<br><small>Has not played yet</small>"
        proj = n(c.get("ptot"), "%.0f") + ("<br><small>%s/g</small>" % n(c.get("pavg")) if c.get("pavg") else "")
        tr = "up" if p["fp7"] and p["avg"] and p["fp7"] > 1.1 * p["avg"] else "dn" if p["fp7"] and p["avg"] and p["fp7"] < 0.9 * p["avg"] else ""
        cells = [
            "<td class='pl' data-v='%s'>%s<div><b>%s</b>%s<br><small>%s · %s</small></div></td>" % (
                p["name"], photo(p["id"]), p["name"], tag, "/".join(p["elig"]), p["team"]),
            td(slot_badge(p["slot"]), dv="FA" if p["slot"] is None else SLOT_NAME.get(p["slot"], "?")),
            td(n(c.get("rank"), "%d"), "key"), td(n(p["avg"]), "key"), td(n(c.get("tot"), "%.0f")),
            td(proj, dv=n(c.get("ptot"), "%.0f")), td(n(p["fp14"])), td(n(p["fp7"]), tr),
            td(p["gp"]), td(n(s.get("MIN"), "%.0f")), td(n(s.get("PTS"))), td(n(s.get("REB"))), td(n(s.get("AST"))),
            td(n(s.get("STL"))), td(n(s.get("BLK"))), td(n(s.get("TOV"))), td(n(s.get("FG3M"))), td(n(p["fgp"], "%.0f%%"))]
        cells += [td(sched.get(d, {}).get(p["team"], ""), "g") for d in days] + [td("<b>%d</b>" % p["games"])]
        rows.append("<tr>%s</tr>" % "".join(cells))
    return "<div class='w'><table><thead>%s</thead><tbody>%s</tbody></table></div>" % (head, "".join(rows))


def lineup_cell(x):
    if not x:
        return "<td class='ln m'>—</td>"
    p, opp = x
    return "<td class='ln'>%s<b>%s</b><br><span class='opp %s'>%s</span></td>" % (
        photo(p["id"]), p["name"].replace(" Jr.", "").split()[-1], "aw" if opp.startswith("@") else "hm", opp)


def lineup_table(players):
    cols = [best_lineup(players, d) for d in CTX["days"]]
    rows = "".join("<tr>%s%s</tr>" % (td("<span class='sl'>%s</span>" % slot), "".join(lineup_cell(c[j]) for c in cols))
                   for j, slot in enumerate(SLOTS))
    return "<div class='w'><table><thead><tr><th>Slot</th>%s</tr></thead><tbody>%s</tbody></table></div>" % (day_header(), rows)


def position_depth(players):
    act = [p for p in players if p["slot"] != 13]
    cnt = {s: (sum(p["primary"] == s for p in act), sum(s in p["elig"] for p in act)) for s in POSES}
    mx = max(1, max(e for _, e in cnt.values()))
    rows = ""
    for s in POSES:
        pr, el = cnt[s]
        rows += "<tr>%s<td><div class='bar'><i style='width:%d%%;background:%s'></i><i style='width:%d%%;background:%s;opacity:.4'></i></div></td>%s</tr>" % (
            td("<b style='color:%s'>%s</b>" % (PCOL[s], s)), pr * 100 / mx, PCOL[s], (el - pr) * 100 / mx, PCOL[s],
            td("<b>%d</b> <small>(%d primary + %d flex)</small>" % (el, pr, el - pr)))
    grid = ""
    for p in sorted(act, key=lambda p: POSES.index(p["primary"]) if p["primary"] in POSES else 9):
        grid += "<tr><td class='pl'>%s<b>%s</b></td>%s</tr>" % (photo(p["id"]), p["name"], "".join(
            "<td style='color:%s;font-size:16px'>%s</td>" % (PCOL[s], "●" if p["primary"] == s else "○" if s in p["elig"] else "")
            for s in POSES))
    order = sorted(POSES, key=lambda s: cnt[s][1])
    note = ("Deepest: <b>%s</b> (%d eligible) · Thinnest: <b>%s</b> (%d eligible). ● primary position, ○ also eligible. "
            "Multi-position players count at every position they can play." % (order[-1], cnt[order[-1]][1], order[0], cnt[order[0]][1]))
    return ("<div class='w'><table><thead><tr><th>Position</th><th>Players</th><th>Eligible</th></tr></thead><tbody>%s</tbody></table></div>"
            "<p><small>%s</small></p><div class='w'><table><thead><tr><th>Player</th>%s</tr></thead><tbody>%s</tbody>"
            "<tfoot><tr><th>Eligible</th>%s</tr></tfoot></table></div>" % (
                rows, note, "".join("<th style='color:%s'>%s</th>" % (PCOL[s], s) for s in POSES), grid,
                "".join("<th>%d</th>" % cnt[s][1] for s in POSES)))


def rec_card(title, color, items):
    body = "".join("<div class='ri'>%s<div><b>%s</b><small>%s</small></div></div>" % (photo(p["id"]), p["name"], txt)
                   for p, txt in items) or "<div class='ri m'>Nobody right now</div>"
    return "<div class='rc' style='--c:%s'><h3>%s</h3>%s</div>" % (color, title, body)


def recs_html(players, is_fa):
    ok = [p for p in players if p["status"] == "" and p["slot"] != 13]
    pct = lambda p: "%+.0f%%" % (100 * (p["fp7"] / p["avg"] - 1))
    hot = [p for p in ok if p["fp7"] and p["avg"] and p["fp7"] > 1.15 * p["avg"] and p["gp"] >= 3]
    cold = [p for p in ok if p["fp7"] and p["avg"] and p["fp7"] < 0.85 * p["avg"] and p["gp"] >= 3]
    hurt = [p for p in players if p["status"]]
    if is_fa:
        top = sorted([p for p in ok if p["gp"]], key=lambda p: -(p["avg"] or 0))[:5]
        stream = sorted([p for p in ok if p["games"]], key=lambda p: -p["val"] * p["games"])[:5]
        cards = [rec_card("▲ Best available", "#2ecc71", [(p, "%s FP/game · %d games" % (n(p["avg"]), p["games"])) for p in top]),
                 rec_card("✚ Streamers (value x games)", "#4d8cf5", [(p, "%d games · %s FP/game" % (p["games"], n(p["avg"]))) for p in stream]),
                 rec_card("🔥 Hot right now", "#ffb43c", [(p, "L7 %s vs %s (%s)" % (n(p["fp7"]), n(p["avg"]), pct(p))) for p in hot[:5]])]
    else:
        drop = sorted([p for p in ok if p["gp"]], key=lambda p: p["val"] * max(p["games"], 1))[:5]
        cards = [rec_card("▼ Drop candidates", "#ff5c7a", [(p, "%s FP/game · %d games in %d days" % (n(p["avg"]), p["games"], DAYS)) for p in drop]),
                 rec_card("▲ Sell high", "#2ecc71", [(p, "L7 %s vs %s (%s)" % (n(p["fp7"]), n(p["avg"]), pct(p))) for p in hot]),
                 rec_card("❄ Cooling off", "#ffb43c", [(p, "L7 %s vs %s (%s)" % (n(p["fp7"]), n(p["avg"]), pct(p))) for p in cold]),
                 rec_card("✚ Injured", "#a07bff", [(p, "%s · return: %s" % (p["status"], p["ret"] or "unknown")) for p in hurt])]
    return "<div class='cards'>%s</div>" % "".join(cards)


TEAM_METRICS = [["wk", "Projected FP, next 7 days", 1, 0], ["avg", "Top-10 AVG FPTS (sum)", 1, 1],
                ["l7", "Top-10 FP L7 (sum)", 1, 1], ["tot", "2027 FPTS (roster)", 1, 0], ["ptot", "2027 PROJ (roster)", 1, 0],
                ["games", "Games, next 7 days", 1, 0], ["PTS", "PTS (top 10)", 1, 1], ["REB", "REB (top 10)", 1, 1],
                ["AST", "AST (top 10)", 1, 1], ["STL", "STL (top 10)", 1, 1], ["BLK", "BLK (top 10)", 1, 1],
                ["TO", "TO (top 10, lower is better)", -1, 1], ["3PM", "3PM (top 10)", 1, 1]] + \
               [["pos" + s, s + " eligible players", 0, 0] for s in POSES] + [["inj", "Injured players", -1, 0]]
PLAYER_METRICS = [["rank", "POS RANK (lower is better)", -1, 0], ["avg", "AVG FPTS", 1, 1], ["tot", "2027 FPTS", 1, 0],
                  ["ptot", "2027 PROJ", 1, 0], ["fp14", "FP L15", 1, 1], ["fp7", "FP L7", 1, 1], ["games", "Games, next 7 days", 1, 0],
                  ["MIN", "MIN", 1, 0], ["PTS", "PTS", 1, 1], ["REB", "REB", 1, 1], ["AST", "AST", 1, 1], ["STL", "STL", 1, 1],
                  ["BLK", "BLK", 1, 1], ["TO", "TO (lower is better)", -1, 1], ["3PM", "3PM", 1, 1], ["FG", "FG%", 1, 0]]


def clean(v):
    return None if v is None or (isinstance(v, float) and v != v) else round(v, 2)


def team_metrics(pl):
    act = [p for p in pl if p["slot"] != 13 and p["status"] != "OUT"]
    top = sorted(act, key=lambda p: -(p["avg"] or 0))[:10]
    live = [p for p in pl if p["slot"] != 13]
    st = lambda k: sum(p["st"].get(k) or 0 for p in top)
    m = dict(wk=sum(x[0]["val"] for d in CTX["days"] for x in best_lineup(pl, d) if x),
             avg=sum(p["avg"] or 0 for p in top), l7=sum(p["fp7"] or p["avg"] or 0 for p in top),
             tot=sum(p["c"].get("tot") or 0 for p in live), ptot=sum(p["c"].get("ptot") or 0 for p in live),
             games=sum(p["games"] for p in act), inj=sum(1 for p in pl if p["status"]),
             PTS=st("PTS"), REB=st("REB"), AST=st("AST"), STL=st("STL"), BLK=st("BLK"), TO=st("TOV"))
    m["3PM"] = st("FG3M")
    for s in POSES:
        m["pos" + s] = sum(s in p["elig"] for p in live)
    return {k: clean(v) for k, v in m.items()}


def player_metrics(p):
    c, s = p["c"], p["st"]
    m = dict(rank=c.get("rank"), avg=p["avg"], tot=c.get("tot"), ptot=c.get("ptot"), fp14=p["fp14"], fp7=p["fp7"],
             games=p["games"], MIN=s.get("MIN"), PTS=s.get("PTS"), REB=s.get("REB"), AST=s.get("AST"), STL=s.get("STL"),
             BLK=s.get("BLK"), TO=s.get("TOV"), FG=p["fgp"])
    m["3PM"] = s.get("FG3M")
    return {k: clean(v) for k, v in m.items()}


def compare_html(views):
    seen, plist = set(), []
    for vid, name, pl, is_fa in views:
        for p in pl:
            if p["id"] not in seen:
                seen.add(p["id"])
                plist.append((p["avg"] or 0, dict(name=p["name"], img=p["id"], v=player_metrics(p),
                              sub="%s · %s" % (p["team"], "Free agent" if is_fa else name.replace(" (you)", "")))))
    data = dict(teams=[dict(name=name, img=None, sub="", v=team_metrics(pl)) for vid, name, pl, is_fa in views if not is_fa],
                players=[d for _, d in sorted(plist, key=lambda x: -x[0])], tm=TEAM_METRICS, pm=PLAYER_METRICS)
    js = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return ("<div class='cmpbar'><select onchange='cmode(this.value)'><option value='teams'>Compare teams</option>"
            "<option value='players'>Compare players</option></select><input id='ca' list='dl' placeholder='Search by name...' oninput='cmp()' onfocus='this.select()' autocomplete='off'>"
            "<input id='cb' list='dl' placeholder='Search by name...' oninput='cmp()' onfocus='this.select()' autocomplete='off'>"
            "<input id='cc' list='dl' placeholder='Add another (optional)...' oninput='cmp()' onfocus='this.select()' autocomplete='off'>"
            "<input id='cd' list='dl' placeholder='Add another (optional)...' oninput='cmp()' onfocus='this.select()' autocomplete='off'>"
            "<input id='ce' list='dl' placeholder='Add another (optional)...' oninput='cmp()' onfocus='this.select()' autocomplete='off'>"
            "<datalist id='dl'></datalist></div>"
            "<div class='w' id='cmpout'></div><script>var DATA=" + js + ";</script>")


def main():
    print("Loading ESPN league...")
    teams, sp = fetch_league()
    mine = next((t for t in teams if MY_TEAM.lower() in t["name"].lower()), None)
    if not mine and SWID:
        mine = next((t for t in teams if SWID in t["owners"]), None)
    if not mine:
        raise RuntimeError("Team '%s' not found. Teams in the league: %s" % (MY_TEAM, ", ".join(t["name"] for t in teams)))
    ids = sorted({e["id"] for t in teams for e in t["entries"]})
    cards, fa, injuries = fetch_cards(ids, sp), fetch_free_agents(sp), fetch_injuries()
    print("Loading NBA stats and schedule...")
    try:
        s_all, s14, s7 = fetch_stats(0), fetch_stats(14), fetch_stats(7)
    except Exception as ex:
        print("NBA stats failed (continuing without them):", ex)
        s_all = s14 = s7 = {}
    now = dt.datetime.now(ZoneInfo("America/New_York"))
    CTX.update(dates=[now.date() + dt.timedelta(i) for i in range(DAYS)])
    CTX["days"] = [d.isoformat() for d in CTX["dates"]]
    CTX["sched"] = fetch_schedule() or fetch_schedule_espn(CTX["days"])

    def make_players(entries):
        out = []
        for en in entries:
            k = norm(en["name"])
            c = merge_cards(cards.get(en["id"]), en["card"])
            inj, r = injuries.get(k, {}), s_all.get(k)
            status = short_status(inj.get("status")) or short_status(c.get("inj")) or short_status(en["inj"])
            gp = int(c.get("gp") or (r["GP"] if r else 0) or 0)
            f_s = fantasy(r) if r else None
            if c["avg"] is None and c["tot"] is not None and gp:
                c["avg"] = c["tot"] / gp
            avg = c["avg"] if c["avg"] is not None else f_s
            f_14 = c["l15"] if c["l15"] is not None else (fantasy(s14[k]) if k in s14 else None)
            f_7 = c["l7"] if c["l7"] is not None else (fantasy(s7[k]) if k in s7 else None)
            val = (0.5 * avg + 0.5 * (f_14 if f_14 is not None else avg)) if avg is not None else (c.get("pavg") or 0)
            pg = c.get("pg") or {}
            if pg.get("PTS") is not None:
                st = dict(MIN=pg.get("MIN"), PTS=pg["PTS"], REB=pg.get("REB"), AST=pg.get("AST"), STL=pg.get("STL"),
                          BLK=pg.get("BLK"), TOV=pg.get("TO"), FG3M=pg.get("3PM"))
                fgp = pg.get("FG")
            elif r is not None and r["GP"]:
                g = r["GP"]
                st = {m: r[m] / g for m in ("MIN", "PTS", "REB", "AST", "STL", "BLK", "TOV", "FG3M")}
                fgp = r["FG_PCT"] * 100
            else:
                st, fgp = {}, None
            out.append(dict(en, c=c, status=status, ret=inj.get("ret"), gp=gp, avg=avg, fp14=f_14, fp7=f_7, val=val,
                            st=st, fgp=fgp, games=sum(en["team"] in CTX["sched"].get(d, {}) for d in CTX["days"])))
        return out

    views = [(t["id"], t["name"] + (" (you)" if t is mine else ""), make_players(t["entries"]), False)
             for t in sorted(teams, key=lambda t: t is not mine)]
    views.append((0, "★ Free Agents", make_players(fa), True))
    cmp_html = compare_html(views)
    opts = "".join("<option value='%d'>%s</option>" % (v[0], v[1]) for v in views)
    sec = {k: [] for k in ("roster", "lineup", "depth", "recs")}
    for vid, name, pl, is_fa in views:
        for k, h in (("roster", roster_table(pl)), ("lineup", lineup_table(pl)),
                     ("depth", position_depth(pl)), ("recs", recs_html(pl, is_fa))):
            sec[k].append("<div class='v v%d' style='display:none'>%s</div>" % (vid, h))
    legend = "<div class='legend'><h4>Legend</h4><dl>%s</dl></div>" % "".join("<dt>%s</dt><dd>%s</dd>" % kv for kv in LEGEND)
    html = "\n".join([
        "<!doctype html>", "<html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'>",
        "<meta name='apple-mobile-web-app-capable' content='yes'><meta name='apple-mobile-web-app-title' content='Fantasy'>"
        "<meta name='apple-mobile-web-app-status-bar-style' content='black-translucent'><meta name='theme-color' content='#000000'>"
        "<link rel='apple-touch-icon' href='espn_fantasy_basketball.png'>",
        "<link rel='preconnect' href='https://fonts.googleapis.com'>",
        "<link href='https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Inter:wght@400;500;600;700&display=swap' rel='stylesheet'>",
        "<title>%s</title>" % mine["name"], "<style>" + CSS + "</style></head><body>",
        "<header>%s<div><b>%s</b><span class='t'>Fantasy dashboard · League %s</span></div></header>" % (
            logo_html(), mine["name"], LEAGUE_ID),
        "<div class='ctl'><label>View</label><select onchange='show(this.value)'>%s</select>"
        "<small>Updated %s (Slovak time) · days follow the NBA schedule (US dates)</small></div>" % (
            opts, dt.datetime.now(ZoneInfo("Europe/Bratislava")).strftime("%d.%m. %H:%M")),
        "<main><h2>Roster</h2><div class='split'><div>%s</div>%s</div>" % ("".join(sec["roster"]), legend),
        "<h2>Recommended Lineup</h2>", *sec["lineup"],
        "<h2>Compare</h2>", cmp_html,
        "<h2>Position Depth</h2>", *sec["depth"],
        "<h2>Recommendations</h2>", *sec["recs"],
        "</main>",
        "<footer>Unofficial personal dashboard, not an ESPN or NBA product.</footer>",
        "<script>" + JS + "show(%d);fill()</script></body></html>" % views[0][0]])
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("Done ->", OUT)
    if not os.environ.get("CI"):
        webbrowser.open("file:///" + OUT.replace("\\", "/"))


if __name__ == "__main__":
    if os.environ.get("CI"):
        main()          # on GitHub Actions: fail loudly, no prompts
    else:
        try:
            main()
        except Exception:
            traceback.print_exc()
        input("\nPress Enter to close this window...")

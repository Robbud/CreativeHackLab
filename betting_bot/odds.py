"""Bookmaker odds: The Odds API (needs ODDS_API_KEY) or a manual JSON file.

Every quote is normalised to:
    {"market": "moneyline"|"handicap"|"total"|"3way",
     "side": "home"|"away"|"draw"|"over"|"under",
     "point": float|None, "price": decimal_odds, "book": str, "updated": iso}
"""
import json
import os
from datetime import datetime, timezone
from urllib.parse import urlencode

from .http import get_json
from .teams import same_team

API = "https://api.the-odds-api.com/v4/sports/{sport}/odds"
SPORT_KEYS = {"NBA": "basketball_nba", "NHL": "icehockey_nhl"}
MARKET_MAP = {"h2h": "moneyline", "spreads": "handicap", "totals": "total",
              "h2h_3_way": "3way"}
MAX_AGE_HOURS = 6
MAX_KICKOFF_DRIFT_HOURS = 3


def _parse_ts(ts):
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def fetch_api(league, regions="eu", bookmakers=None, markets="h2h,spreads,totals"):
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        return None
    params = {"apiKey": key, "regions": regions, "markets": markets,
              "oddsFormat": "decimal", "dateFormat": "iso"}
    if bookmakers:
        params = {k: v for k, v in params.items() if k != "regions"}
        params["bookmakers"] = bookmakers
    events = get_json(API.format(sport=SPORT_KEYS[league]) + "?" + urlencode(params))
    out = []
    now = datetime.now(timezone.utc)
    for ev in events:
        quotes = []
        for bk in ev.get("bookmakers", []):
            for mk in bk.get("markets", []):
                market = MARKET_MAP.get(mk["key"])
                if not market:
                    continue
                upd = _parse_ts(mk.get("last_update") or bk.get("last_update"))
                if upd and (now - upd).total_seconds() > MAX_AGE_HOURS * 3600:
                    continue  # stale line
                for o in mk["outcomes"]:
                    side = _side(o["name"], ev["home_team"], ev["away_team"], market)
                    if side:
                        quotes.append({"market": market, "side": side,
                                       "point": o.get("point"), "price": float(o["price"]),
                                       "book": bk["title"], "updated": upd.isoformat() if upd else None})
        out.append({"home": ev["home_team"], "away": ev["away_team"],
                    "commence": ev.get("commence_time"), "quotes": quotes})
    return out


def _side(name, home, away, market):
    n = name.lower()
    if market == "total":
        return "over" if n == "over" else "under" if n == "under" else None
    if n == "draw":
        return "draw"
    if name == home:
        return "home"
    if name == away:
        return "away"
    return None


def load_file(path):
    """Manual odds, e.g. copied from your own bookmaker. See README."""
    with open(path) as fh:
        raw = json.load(fh)
    out = []
    for ev in raw:
        book = ev.get("book", "manual")
        quotes = [{"market": q["market"], "side": q["side"],
                   "point": q.get("point"), "price": float(q["price"]),
                   "book": q.get("book", book), "updated": None}
                  for q in ev["lines"]]
        out.append({"home": ev["home"], "away": ev["away"],
                    "commence": ev.get("commence"), "quotes": quotes})
    return out


def attach(games, events):
    """Match odds events to official games; returns list of warnings."""
    warnings = []
    used = set()
    for g in games:
        g["quotes"] = []
        for i, ev in enumerate(events):
            h = same_team(ev["home"], g["home"]["full"], g["home"]["nick"])
            a = same_team(ev["away"], g["away"]["full"], g["away"]["nick"])
            if not (h and a):
                if (same_team(ev["home"], g["away"]["full"], g["away"]["nick"])
                        and same_team(ev["away"], g["home"]["full"], g["home"]["nick"])):
                    warnings.append(f'{g["league"]} {g["away"]["abbrev"]}@{g["home"]["abbrev"]}: '
                                    "odds feed has home/away reversed vs official schedule - skipped")
                    used.add(i)
                continue
            ko, st = _parse_ts(ev.get("commence")), _parse_ts(g.get("start_utc"))
            if ko and st and abs((ko - st).total_seconds()) > MAX_KICKOFF_DRIFT_HOURS * 3600:
                continue  # same teams, different date
            g["quotes"] = ev["quotes"]
            used.add(i)
            break
        if not g["quotes"]:
            warnings.append(f'{g["league"]} {g["away"]["abbrev"]}@{g["home"]["abbrev"]}: no odds found')
    for i, ev in enumerate(events):
        if i not in used:
            ko = _parse_ts(ev.get("commence"))
            if ko is None or any(abs((ko - _parse_ts(g["start_utc"])).total_seconds()) < 12 * 3600
                                 for g in games if g.get("start_utc")):
                warnings.append(f'Odds event {ev["away"]} @ {ev["home"]} not on official schedule - ignored')
    return warnings

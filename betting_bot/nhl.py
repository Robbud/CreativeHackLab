"""Official NHL data: api-web.nhle.com (the NHL's own public API)."""
from datetime import date as _date

from .http import get_json

BASE = "https://api-web.nhle.com/v1"
GAME_TYPES = {1: "preseason", 2: "regular", 3: "playoffs"}


def schedule(day):
    """Games on `day` (YYYY-MM-DD, NHL local date)."""
    data = get_json(f"{BASE}/schedule/{day}")
    games = []
    for wk in data.get("gameWeek", []):
        if wk.get("date") != day:
            continue
        for g in wk.get("games", []):
            games.append({
                "league": "NHL",
                "id": g["id"],
                "type": GAME_TYPES.get(g.get("gameType"), str(g.get("gameType"))),
                "start_utc": g.get("startTimeUTC"),
                "state": g.get("gameState"),
                "venue": (g.get("venue") or {}).get("default"),
                "home": _team(g["homeTeam"]),
                "away": _team(g["awayTeam"]),
            })
    return games


def _team(t):
    place = (t.get("placeName") or {}).get("default", "")
    nick = (t.get("commonName") or {}).get("default", "")
    return {"abbrev": t.get("abbrev"), "full": f"{place} {nick}".strip(), "nick": nick}


def _standings_rows(day):
    rows = get_json(f"{BASE}/standings/{day}").get("standings", [])
    out = {}
    for r in rows:
        ab = r["teamAbbrev"]["default"]
        out[ab] = {"gp": r.get("gamesPlayed", 0), "gf": r.get("goalFor", 0),
                   "ga": r.get("goalAgainst", 0),
                   "l10_gf": r.get("l10GoalsFor"), "l10_ga": r.get("l10GoalsAgainst"),
                   "record": f'{r.get("wins", 0)}-{r.get("losses", 0)}-{r.get("otLosses", 0)}'}
    return out


def _previous_season_end(day):
    seasons = get_json(f"{BASE}/standings-season").get("seasons", [])
    ends = [s["standingsEnd"] for s in seasons if s.get("standingsEnd", "") < day]
    return max(ends) if ends else None


PRIOR_WEIGHT_GAMES = 20  # how many games last season's rates are "worth"


def team_strengths(day):
    """Per-team gp/gf/ga blended with last season's final standings.

    Early in a season current numbers are noise, so last season's per-game
    rates are folded in as PRIOR_WEIGHT_GAMES pseudo-games (scaled down to 8
    to account for roster turnover).
    """
    yesterday = _date.fromordinal(_date.fromisoformat(day).toordinal() - 1).isoformat()
    try:
        current = _standings_rows(yesterday)
    except Exception:
        current = {}
    prev_end = _previous_season_end(day)
    prior = _standings_rows(prev_end) if prev_end else {}
    teams = {}
    for ab in set(current) | set(prior):
        cur = current.get(ab, {"gp": 0, "gf": 0, "ga": 0})
        if cur["gp"] < 1 and ab not in prior:
            continue
        gp, gf, ga = cur["gp"], cur["gf"], cur["ga"]
        p = prior.get(ab)
        if p and p["gp"]:
            w = 8 if gp >= PRIOR_WEIGHT_GAMES else PRIOR_WEIGHT_GAMES - gp * 0.6
            gf += p["gf"] / p["gp"] * w
            ga += p["ga"] / p["gp"] * w
            gp += w
        teams[ab] = {"gp": gp, "gf": gf, "ga": ga,
                     "record": cur.get("record", "0-0-0"),
                     "current_gp": cur["gp"]}
    tot_gp = sum(t["gp"] for t in teams.values()) or 1
    league_gpg = sum(t["gf"] for t in teams.values()) / tot_gp
    return teams, league_gpg, {"prior_season_end": prev_end}

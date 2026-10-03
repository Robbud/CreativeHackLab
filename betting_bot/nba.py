"""Official NBA data: cdn.nba.com schedule + stats.nba.com team ratings."""
from datetime import datetime
from urllib.parse import urlencode

from .http import get_json

SCHEDULE_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json"
STATS_URL = "https://stats.nba.com/stats/leaguedashteamstats"
STATS_HEADERS = {
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}
GAME_TYPES = {"001": "preseason", "002": "regular", "003": "all-star",
              "004": "playoffs", "005": "play-in", "006": "cup-final"}


def schedule(day):
    data = get_json(SCHEDULE_URL)
    want = datetime.strptime(day, "%Y-%m-%d").strftime("%m/%d/%Y")
    games = []
    for gd in data["leagueSchedule"]["gameDates"]:
        if not gd["gameDate"].startswith(want):
            continue
        for g in gd["games"]:
            games.append({
                "league": "NBA",
                "id": g["gameId"],
                "type": GAME_TYPES.get(g["gameId"][:3], g["gameId"][:3]),
                "start_utc": g.get("gameDateTimeUTC"),
                "state": g.get("gameStatusText"),
                "venue": g.get("arenaName"),
                "label": g.get("gameLabel") or g.get("gameSubLabel"),
                "home": _team(g["homeTeam"]),
                "away": _team(g["awayTeam"]),
            })
    return games


def _team(t):
    return {"abbrev": t.get("teamTricode"),
            "full": f'{t.get("teamCity", "")} {t.get("teamName", "")}'.strip(),
            "nick": t.get("teamName", ""), "id": t.get("teamId")}


def season_string(day):
    d = datetime.strptime(day, "%Y-%m-%d")
    y = d.year if d.month >= 8 else d.year - 1
    return f"{y}-{(y + 1) % 100:02d}"


def _ratings(season, season_type="Regular Season"):
    params = {
        "MeasureType": "Advanced", "PerMode": "PerGame", "Season": season,
        "SeasonType": season_type, "LeagueID": "00", "LastNGames": 0, "Month": 0,
        "OpponentTeamID": 0, "PaceAdjust": "N", "Period": 0, "PlusMinus": "N",
        "Rank": "N", "TeamID": 0, "PORound": 0, "TwoWay": 0, "Conference": "",
        "DateFrom": "", "DateTo": "", "Division": "", "GameScope": "",
        "GameSegment": "", "Location": "", "Outcome": "", "PlayerExperience": "",
        "PlayerPosition": "", "SeasonSegment": "", "ShotClockRange": "",
        "StarterBench": "", "VsConference": "", "VsDivision": "",
    }
    data = get_json(f"{STATS_URL}?{urlencode(params)}", headers=STATS_HEADERS)
    rs = data["resultSets"][0]
    idx = {h: i for i, h in enumerate(rs["headers"])}
    out = {}
    for row in rs["rowSet"]:
        out[row[idx["TEAM_ID"]]] = {
            "gp": row[idx["GP"]], "ortg": row[idx["OFF_RATING"]],
            "drtg": row[idx["DEF_RATING"]], "pace": row[idx["PACE"]],
            "name": row[idx["TEAM_NAME"]],
        }
    return out


PRIOR_GAMES = 15


def team_ratings(day):
    """Current-season ratings blended with last season (PRIOR_GAMES weight)."""
    season = season_string(day)
    y = int(season[:4]) - 1
    prev = f"{y}-{(y + 1) % 100:02d}"
    try:
        cur = _ratings(season)
    except Exception:
        cur = {}
    prior = _ratings(prev)
    teams = {}
    for tid in set(cur) | set(prior):
        c, p = cur.get(tid), prior.get(tid)
        if c and p:
            w = PRIOR_GAMES * max(0.3, 1 - c["gp"] / 40)
            blend = {k: (c[k] * c["gp"] + p[k] * w) / (c["gp"] + w)
                     for k in ("ortg", "drtg", "pace")}
            blend["gp"] = c["gp"] + w
        else:
            src = c or p
            blend = {k: src[k] for k in ("ortg", "drtg", "pace", "gp")}
        blend["current_gp"] = c["gp"] if c else 0
        teams[tid] = blend
    n = len(teams) or 1
    league = {k: sum(t[k] for t in teams.values()) / n for k in ("ortg", "drtg", "pace")}
    league["ortg"] = league["drtg"] = (league["ortg"] + league["drtg"]) / 2
    league["gp"] = 0
    return teams, league, {"season": season, "prior_season": prev}

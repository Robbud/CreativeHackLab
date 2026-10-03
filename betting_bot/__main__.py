"""Tonight's NBA/NHL picks.

    python -m betting_bot                       # today (US/Eastern), both leagues
    python -m betting_bot --date 2026-10-03 --league nhl
    python -m betting_bot --odds-file my_odds.json
"""
import argparse
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from . import models, nba, nhl, odds, picks
from .http import FetchError


def fair_odds(p):
    return f"{1 / p:.2f}" if p > 0 else "-"


def run_nhl(day, args, out, warn):
    games = nhl.schedule(day)
    if not games:
        out.append("_No NHL games on the official schedule._\n")
        return []
    teams, lg_gpg, meta = nhl.team_strengths(day)
    out.append(f"League scoring baseline: {lg_gpg:.2f} goals/team/game "
               f"(prior season through {meta['prior_season_end']}).\n")
    priced = []
    for g in games:
        h, a = teams.get(g["home"]["abbrev"]), teams.get(g["away"]["abbrev"])
        if not (h and a):
            warn.append(f"NHL {g['away']['abbrev']}@{g['home']['abbrev']}: missing official team stats")
            continue
        lam_h, lam_a = models.nhl_expected_goals(h, a, lg_gpg)
        g["outcomes"] = models.nhl_outcomes(lam_h, lam_a)
        g["three_way"] = models.nhl_regulation_3way(lam_h, lam_a)
        g["proj"] = (lam_h, lam_a)
        g["records"] = (h["record"], a["record"])
        g["sample"] = min(h["current_gp"], a["current_gp"])
        priced.append(g)
    return priced


def run_nba(day, args, out, warn):
    games = nba.schedule(day)
    if not games:
        out.append("_No NBA games on the official schedule._\n")
        return []
    teams, league, meta = nba.team_ratings(day)
    out.append(f"Ratings: {meta['season']} blended with {meta['prior_season']} "
               f"(league ORtg {league['ortg']:.1f}, pace {league['pace']:.1f}).\n")
    priced = []
    for g in games:
        h, a = teams.get(g["home"]["id"]), teams.get(g["away"]["id"])
        if not (h and a):
            warn.append(f"NBA {g['away']['abbrev']}@{g['home']['abbrev']}: missing official ratings "
                        "(non-NBA opponent?)")
            continue
        pts_h, pts_a = models.nba_expected_points(h, a, league)
        g["outcomes"] = models.nba_outcomes(pts_h, pts_a)
        g["three_way"] = None
        g["proj"] = (pts_h, pts_a)
        g["records"] = ("", "")
        g["sample"] = min(h["current_gp"], a["current_gp"])
        priced.append(g)
    return priced


def report_game(g, args, out, all_picks):
    tz = ZoneInfo(args.tz)
    start = datetime.fromisoformat(g["start_utc"].replace("Z", "+00:00")).astimezone(tz)
    eh, ea = g["outcomes"].expected()
    ml = g["outcomes"].moneyline()
    unit = "goals" if g["league"] == "NHL" else "pts"
    out.append(f"### {g['away']['full']} @ {g['home']['full']}  "
               f"({start:%H:%M %Z}, {g['type']}{', ' + g['venue'] if g.get('venue') else ''})")
    out.append(f"- Projection: {g['home']['abbrev']} {eh:.2f} - {ea:.2f} {g['away']['abbrev']} "
               f"(total {eh + ea:.2f} {unit}, margin {eh - ea:+.2f})")
    out.append(f"- Fair moneyline: {g['home']['abbrev']} {fair_odds(ml['home'])} ({ml['home']:.1%}) / "
               f"{g['away']['abbrev']} {fair_odds(ml['away'])} ({ml['away']:.1%})")
    if g["three_way"]:
        tw = g["three_way"]
        out.append(f"- 60-min 1X2: {tw['home']:.1%} / draw {tw['draw']:.1%} / {tw['away']:.1%}")
    if g["sample"] < 5:
        out.append(f"- Early-season sample ({g['sample']} GP) - leaning on last season's numbers.")

    if g["type"] != "regular" and not args.include_preseason:
        out.append(f"- **No picks: {g['type']} game** (rotations/minutes unknown; "
                   "use --include-preseason to override).\n")
        return
    if not g.get("quotes"):
        out.append("- No odds attached - projection only.\n")
        return
    rows = picks.grade(g, g["outcomes"], g["three_way"])
    chosen = picks.select(rows, args.min_ev)
    if not chosen:
        out.append("- **Pass** - no line clears the +EV threshold.\n")
        return
    for r in chosen:
        stake = r["stake"] * args.bankroll
        out.append(f"- **PICK {picks.label(g, r)} @ {r['price']:.2f}** ({r['book']}) - "
                   f"win {r['p']:.1%} (model {r['model_p']:.1%}, market {r['market_p']:.1%}), "
                   f"EV {r['ev']:+.1%}, stake {r['stake']:.2%} = {stake:.2f}")
        all_picks.append((g, r))
    out.append("")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="betting_bot", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="YYYY-MM-DD (default: today in US/Eastern)")
    ap.add_argument("--league", nargs="+", default=["nba", "nhl"], choices=["nba", "nhl"])
    ap.add_argument("--odds-file", help="manual odds JSON (see README)")
    ap.add_argument("--regions", default="eu", help="Odds API regions (us, uk, eu, au)")
    ap.add_argument("--bookmakers", help="Odds API bookmaker keys, comma separated")
    ap.add_argument("--min-ev", type=float, default=picks.MIN_EV)
    ap.add_argument("--bankroll", type=float, default=1000.0)
    ap.add_argument("--tz", default="America/New_York", help="display time zone")
    ap.add_argument("--include-preseason", action="store_true")
    ap.add_argument("--out", help="also write the report to this markdown file")
    args = ap.parse_args(argv)
    day = args.date or datetime.now(ZoneInfo("America/New_York")).date().isoformat()

    out = [f"# NBA / NHL betting card - {day}", ""]
    warn, all_picks = [], []
    manual = odds.load_file(args.odds_file) if args.odds_file else None
    if manual is None and not os.environ.get("ODDS_API_KEY"):
        warn.append("No ODDS_API_KEY and no --odds-file: showing projections/fair lines only.")

    for league, runner in (("NHL", run_nhl), ("NBA", run_nba)):
        if league.lower() not in args.league:
            continue
        out.append(f"## {league}")
        try:
            games = runner(day, args, out, warn)
        except FetchError as exc:
            out.append(f"_Official {league} data unavailable: {exc}_\n")
            warn.append(f"{league}: official data could not be fetched - no picks made.")
            continue
        events = manual if manual is not None else odds.fetch_api(
            league, args.regions, args.bookmakers,
            "h2h,spreads,totals" + (",h2h_3_way" if league == "NHL" else ""))
        if events:
            warn.extend(odds.attach(games, events))
        for g in games:
            report_game(g, args, out, all_picks)

    out.append("## Card summary")
    if all_picks:
        for g, r in sorted(all_picks, key=lambda x: -x[1]["ev"]):
            out.append(f"- {g['league']} {g['away']['abbrev']}@{g['home']['abbrev']}: "
                       f"{picks.label(g, r)} @ {r['price']:.2f} (EV {r['ev']:+.1%}, "
                       f"stake {r['stake'] * args.bankroll:.2f})")
    else:
        out.append("- No bets. Passing is a position.")
    out.append("")
    out.append("## Checks before betting")
    out.append("- NHL: confirm starting goalies (team beat reporters / morning skate); "
               "a backup start can move a line 20-40 cents.")
    out.append("- NBA: read the official NBA injury report (official.nba.com) - "
               "rest days and late scratches are not in the model.")
    out.append("- Re-price if the line has moved since the report was generated.")
    if warn:
        out.append("\n## Warnings")
        out.extend(f"- {w}" for w in warn)
    out.append("\n_Model output, not financial advice. Bet only what you can afford to lose._")

    text = "\n".join(out)
    print(text)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

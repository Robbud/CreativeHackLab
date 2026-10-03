# NBA / NHL betting bot

Prices tonight's NBA and NHL games from **official league data**, compares the
prices with bookmaker odds, and only recommends bets with positive expected value.

## Data sources

| What | Source |
|---|---|
| NHL schedule and standings (GF/GA, record) | `api-web.nhle.com` (official NHL API) |
| NBA schedule | `cdn.nba.com` (official NBA schedule feed) |
| NBA ratings (ORtg, DRtg, pace) | `stats.nba.com` (official NBA stats) |
| Odds | The Odds API (`ODDS_API_KEY`) **or** a manual JSON file from your own bookmaker |

If an official feed can't be reached, the bot makes **no picks for that league**.
It never guesses.

## Markets

* **Moneyline**: winner, including OT/SO.
* **Handicap**: puck line ±1.5 and NBA point spreads, including integer lines that push.
* **Totals**: over/under goals and points, including OT, the way bookmakers grade them.
* **NHL 60-minute 1X2**: regulation result, draw included.

## Model

* **NHL:** Poisson goals built from attack and defence strength relative to the league average, with a home-ice boost. The draw rate is inflated to match the real NHL regulation tie rate (~22%). A regulation tie becomes a one-goal OT/SO win, which is how books grade totals and puck lines.
* **NBA:** Possessions come from both teams' pace. Points are ORtg × opponent DRtg / league average, plus ~2.2 points of home court. Margin and total are modelled as normals (SD 12.5 and 18.5), discretised to integer scores.
* **Early season:** current-season stats are blended with last season's and regressed toward the league mean.
* **Bet selection:**
  1. Remove the vig from every book's two-way and three-way market, then average the books into a market consensus.
  2. Final probability = 40% model + 60% market.
  3. Bet only when EV ≥ +3% at a price between 1.40 and 4.00.
  4. Skip any line where model and market disagree by more than 15 points; that gap usually means missing news, such as an injury or the starting goalie.
  5. Stake with quarter-Kelly, capped at 2% of bankroll.
  6. Make no picks on preseason games unless `--include-preseason` is set.

## Usage

```bash
# from the repo root
export ODDS_API_KEY=...            # https://the-odds-api.com (free tier works)
python3 -m betting_bot                                   # today, both leagues
python3 -m betting_bot --date 2026-10-10 --league nhl --bankroll 500
python3 -m betting_bot --bookmakers pinnacle,betsson     # specific books
python3 -m betting_bot --odds-file betting_bot/sample_odds.json   # your own book's prices
python3 -m betting_bot --out card.md                     # save the report
python3 -m unittest betting_bot.tests.test_bot           # tests (offline)
```

The manual odds format is in `sample_odds.json`:
* `market` is one of `moneyline`, `handicap`, `total` or `3way`.
* `side` is one of `home`, `away`, `draw`, `over` or `under`.
* Handicap points are from that side's perspective.
* Include both sides of each market, so the vig can be removed.

## Check manually before betting

* **NHL starting goalies:** not in any official pre-game feed.
* **NBA injuries:** check the official NBA injury report.
* **Line movement since the report was generated.**

Model output is not financial advice. Bet responsibly.

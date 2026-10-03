import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from betting_bot import __main__ as cli
from betting_bot import models, nba, nhl, odds, picks
from betting_bot.teams import same_team


def nhl_standing(ab, place, nick, gp, gf, ga):
    return {"teamAbbrev": {"default": ab}, "placeName": {"default": place},
            "teamCommonName": {"default": nick}, "gamesPlayed": gp,
            "goalFor": gf, "goalAgainst": ga, "wins": gp // 2, "losses": gp // 3, "otLosses": 0}


NHL_FIXTURES = {
    "schedule/2026-10-10": {"gameWeek": [{"date": "2026-10-10", "games": [{
        "id": 2026020001, "gameType": 2, "startTimeUTC": "2026-10-10T23:00:00Z",
        "gameState": "FUT", "venue": {"default": "Scotiabank Arena"},
        "homeTeam": {"abbrev": "TOR", "placeName": {"default": "Toronto"}, "commonName": {"default": "Maple Leafs"}},
        "awayTeam": {"abbrev": "MTL", "placeName": {"default": "Montréal"}, "commonName": {"default": "Canadiens"}},
    }]}]},
    "standings/2026-10-09": {"standings": [
        nhl_standing("TOR", "Toronto", "Maple Leafs", 3, 12, 7),
        nhl_standing("MTL", "Montréal", "Canadiens", 3, 8, 10)]},
    "standings-season": {"seasons": [{"id": 20252026, "standingsEnd": "2026-04-16"},
                                     {"id": 20262027, "standingsEnd": "2027-04-15"}]},
    "standings/2026-04-16": {"standings": [
        nhl_standing("TOR", "Toronto", "Maple Leafs", 82, 270, 230),
        nhl_standing("MTL", "Montréal", "Canadiens", 82, 245, 250)]},
}


def fake_nhl(url, headers=None, **kw):
    return NHL_FIXTURES[url.split("/v1/")[1]]


class ModelTests(unittest.TestCase):
    def test_nhl_probabilities_sum_and_shape(self):
        o = models.nhl_outcomes(3.2, 2.8)
        ml = o.moneyline()
        self.assertAlmostEqual(ml["home"] + ml["away"], 1, places=9)
        self.assertGreater(ml["home"], 0.5)
        tw = models.nhl_regulation_3way(3.0, 3.0)
        self.assertTrue(0.19 < tw["draw"] < 0.25)  # realistic NHL tie rate
        w, p, l = o.handicap("home", -1.5)
        w2, p2, l2 = o.handicap("away", 1.5)
        self.assertAlmostEqual(w, l2)
        self.assertEqual(p, 0)

    def test_integer_total_has_push(self):
        o = models.nhl_outcomes(3.0, 3.0)
        w, p, l = o.total("over", 6)
        self.assertGreater(p, 0.05)
        self.assertAlmostEqual(w + p + l, 1)

    def test_nba_symmetric(self):
        o = models.nba_outcomes(110.25, 110.25)  # mean total 220.5
        ml = o.moneyline()
        self.assertAlmostEqual(ml["home"], 0.5, places=2)
        w, p, _ = o.total("over", 220.5)
        self.assertAlmostEqual(w, 0.5, places=2)
        self.assertEqual(p, 0)

    def test_nba_spread_matches_normal(self):
        o = models.nba_outcomes(115, 108)  # margin 7
        w, _, _ = o.handicap("home", -6.5)
        expected = 1 - models.norm_cdf(6.5, 7, models.NBA_MARGIN_SD)
        self.assertAlmostEqual(w, expected, places=2)


class PickTests(unittest.TestCase):
    def test_market_devig_and_value(self):
        game = {"home": {"abbrev": "H"}, "away": {"abbrev": "A"}, "quotes": [
            {"market": "moneyline", "side": "home", "point": None, "price": 1.80, "book": "X"},
            {"market": "moneyline", "side": "away", "point": None, "price": 2.10, "book": "X"},
            {"market": "moneyline", "side": "home", "point": None, "price": 1.95, "book": "Y"},
            {"market": "moneyline", "side": "away", "point": None, "price": 1.95, "book": "Y"},
        ]}
        fair = picks.market_fair(game["quotes"])
        self.assertAlmostEqual(fair[("moneyline", "home", None)] + fair[("moneyline", "away", None)], 1)
        o = models.nhl_outcomes(3.6, 2.6)
        rows = picks.grade(game, o)
        best_home = [r for r in rows if r["side"] == "home"][0]
        self.assertEqual(best_home["price"], 1.95)  # line shopping
        self.assertLessEqual(best_home["stake"], picks.MAX_STAKE)

    def test_big_disagreement_is_not_picked(self):
        row = {"ev": 0.2, "price": 2.0, "market_p": 0.3, "disagree": 0.3, "market": "moneyline"}
        self.assertEqual(picks.select([row]), [])


class MatchingTests(unittest.TestCase):
    def test_names(self):
        self.assertTrue(same_team("Montreal Canadiens", "Montréal Canadiens", "Canadiens"))
        self.assertTrue(same_team("Los Angeles Clippers", "LA Clippers", "Clippers"))
        self.assertTrue(same_team("Portland Trail Blazers", "Portland Trail Blazers", "Trail Blazers"))
        self.assertFalse(same_team("New York Rangers", "New York Islanders", "Islanders"))


class EndToEndTests(unittest.TestCase):
    @mock.patch("betting_bot.nhl.get_json", side_effect=fake_nhl)
    def test_nhl_card_with_manual_odds(self, _):
        lines = [{"home": "Toronto Maple Leafs", "away": "Montreal Canadiens", "book": "Book",
                  "commence": "2026-10-10T23:00:00Z", "lines": [
                      {"market": "moneyline", "side": "home", "price": 1.70},
                      {"market": "moneyline", "side": "away", "price": 2.25},
                      {"market": "total", "side": "over", "point": 6.5, "price": 2.05},
                      {"market": "total", "side": "under", "point": 6.5, "price": 1.80},
                      {"market": "handicap", "side": "home", "point": -1.5, "price": 2.60},
                      {"market": "handicap", "side": "away", "point": 1.5, "price": 1.50}]}]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(lines, fh)
        buf = io.StringIO()
        with redirect_stdout(buf), mock.patch.dict(os.environ, {}, clear=False):
            cli.main(["--date", "2026-10-10", "--league", "nhl", "--odds-file", fh.name])
        os.unlink(fh.name)
        text = buf.getvalue()
        self.assertIn("Montréal Canadiens @ Toronto Maple Leafs", text)
        self.assertIn("Projection: TOR", text)
        self.assertIn("60-min 1X2", text)
        self.assertNotIn("no odds found", text)

    def test_reversed_home_away_flagged(self):
        g = {"league": "NHL", "start_utc": "2026-10-10T23:00:00Z",
             "home": {"abbrev": "TOR", "full": "Toronto Maple Leafs", "nick": "Maple Leafs"},
             "away": {"abbrev": "MTL", "full": "Montréal Canadiens", "nick": "Canadiens"}}
        ev = {"home": "Montreal Canadiens", "away": "Toronto Maple Leafs",
              "commence": "2026-10-10T23:00:00Z", "quotes": [{"x": 1}]}
        warnings = odds.attach([g], [ev])
        self.assertEqual(g["quotes"], [])
        self.assertTrue(any("reversed" in w for w in warnings))

    def test_nba_season_string(self):
        self.assertEqual(nba.season_string("2026-10-03"), "2026-27")
        self.assertEqual(nba.season_string("2027-03-01"), "2026-27")


if __name__ == "__main__":
    unittest.main()

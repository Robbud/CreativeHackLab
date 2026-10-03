"""Pricing models.

NHL: independent Poisson goals with attack/defence strengths, OT/SO resolved
     as a coin flip that adds one goal to the winner (how books grade totals).
NBA: normal distributions for margin and total built from pace and
     offensive/defensive ratings.

Every model returns an `Outcomes` object able to price moneyline, spread
(handicap) and total lines, including integer lines that can push.
"""
import math

# ---------------------------------------------------------------- helpers


def poisson_pmf(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def norm_cdf(x, mu=0.0, sd=1.0):
    return 0.5 * (1.0 + math.erf((x - mu) / (sd * math.sqrt(2.0))))


def shrink(value, games, prior, k):
    """Regress a per-game rate toward `prior` with `k` pseudo-games."""
    return (value * games + prior * k) / (games + k)


class Outcomes:
    """Discrete joint distribution of final (home, away) scores."""

    def __init__(self, dist, draw_possible=False):
        self.dist = dist  # {(home, away): prob}, final scores incl. OT
        self.draw_possible = draw_possible

    def _sum(self, pred):
        return sum(p for (h, a), p in self.dist.items() if pred(h, a))

    def moneyline(self):
        return {"home": self._sum(lambda h, a: h > a),
                "away": self._sum(lambda h, a: a > h)}

    def handicap(self, side, line):
        """(win, push, loss) for `side` ('home'/'away') taking `line`."""
        sign = 1 if side == "home" else -1
        win = self._sum(lambda h, a: sign * (h - a) + line > 1e-9)
        push = self._sum(lambda h, a: abs(sign * (h - a) + line) <= 1e-9)
        return win, push, 1 - win - push

    def total(self, side, line):
        if side == "over":
            win = self._sum(lambda h, a: h + a - line > 1e-9)
        else:
            win = self._sum(lambda h, a: line - (h + a) > 1e-9)
        push = self._sum(lambda h, a: abs(h + a - line) <= 1e-9)
        return win, push, 1 - win - push

    def expected(self):
        eh = sum(h * p for (h, a), p in self.dist.items())
        ea = sum(a * p for (h, a), p in self.dist.items())
        return eh, ea


# ---------------------------------------------------------------- NHL

NHL_HOME_EDGE = 1.035   # multiplicative goal-rate boost for the home side
NHL_SHRINK_GAMES = 12   # pseudo-games of league-average regression
NHL_MAX_GOALS = 13


def nhl_expected_goals(home, away, league_gpg):
    """home/away: dicts with gp, gf, ga (season totals)."""
    def rates(t):
        gp = max(t["gp"], 0)
        gf = t["gf"] / gp if gp else league_gpg
        ga = t["ga"] / gp if gp else league_gpg
        return (shrink(gf, gp, league_gpg, NHL_SHRINK_GAMES),
                shrink(ga, gp, league_gpg, NHL_SHRINK_GAMES))

    hgf, hga = rates(home)
    agf, aga = rates(away)
    lam_h = league_gpg * (hgf / league_gpg) * (aga / league_gpg) * NHL_HOME_EDGE
    lam_a = league_gpg * (agf / league_gpg) * (hga / league_gpg) / NHL_HOME_EDGE
    return lam_h, lam_a


# Independent Poisson under-prices 60-minute ties (~16% vs ~22-23% seen in
# the NHL); inflate the diagonal and renormalise.
NHL_DRAW_INFLATION = 1.35


def nhl_regulation_matrix(lam_h, lam_a):
    ph = [poisson_pmf(i, lam_h) for i in range(NHL_MAX_GOALS)]
    pa = [poisson_pmf(i, lam_a) for i in range(NHL_MAX_GOALS)]
    m = {}
    for h in range(NHL_MAX_GOALS):
        for a in range(NHL_MAX_GOALS):
            m[(h, a)] = ph[h] * pa[a] * (NHL_DRAW_INFLATION if h == a else 1.0)
    norm = sum(m.values())
    return {k: v / norm for k, v in m.items()}


def nhl_outcomes(lam_h, lam_a, home_ot_share=0.52):
    """Final-score distribution. A regulation tie becomes a 1-goal OT/SO win."""
    dist = {}
    for (h, a), p in nhl_regulation_matrix(lam_h, lam_a).items():
        if h == a:
            dist[(h + 1, a)] = dist.get((h + 1, a), 0) + p * home_ot_share
            dist[(h, a + 1)] = dist.get((h, a + 1), 0) + p * (1 - home_ot_share)
        else:
            dist[(h, a)] = dist.get((h, a), 0) + p
    return Outcomes(dist)


def nhl_regulation_3way(lam_h, lam_a):
    """60-minute result probabilities (home / draw / away)."""
    out = {"home": 0.0, "draw": 0.0, "away": 0.0}
    for (h, a), p in nhl_regulation_matrix(lam_h, lam_a).items():
        out["home" if h > a else "draw" if h == a else "away"] += p
    return out


# ---------------------------------------------------------------- NBA

NBA_HOME_COURT = 2.2     # points
NBA_MARGIN_SD = 12.5
NBA_TOTAL_SD = 18.5
NBA_SHRINK_GAMES = 10


def nba_expected_points(home, away, league):
    """home/away/league: dicts with gp, ortg, drtg, pace."""
    def reg(t, key):
        return shrink(t[key], t["gp"], league[key], NBA_SHRINK_GAMES)

    poss = reg(home, "pace") * reg(away, "pace") / league["pace"]
    lg = league["ortg"]
    pts_h = poss * reg(home, "ortg") * reg(away, "drtg") / lg / 100
    pts_a = poss * reg(away, "ortg") * reg(home, "drtg") / lg / 100
    return pts_h + NBA_HOME_COURT / 2, pts_a - NBA_HOME_COURT / 2


def nba_outcomes(pts_h, pts_a, margin_sd=NBA_MARGIN_SD, total_sd=NBA_TOTAL_SD):
    """Discretised joint distribution of (home, away) points.

    Margin and total are treated as independent normals; integer scores
    are produced on a grid so integer lines push correctly.  Ties are
    removed (NBA goes to OT) by splitting them to +/-1 by win probability.
    """
    mu_m, mu_t = pts_h - pts_a, pts_h + pts_a
    dist = {}
    m_lo, m_hi = int(mu_m - 5 * margin_sd), int(mu_m + 5 * margin_sd)
    t_lo, t_hi = int(mu_t - 5 * total_sd), int(mu_t + 5 * total_sd)
    pt = {t: norm_cdf(t + 0.5, mu_t, total_sd) - norm_cdf(t - 0.5, mu_t, total_sd)
          for t in range(t_lo, t_hi + 1)}
    parity_mass = [sum(p for t, p in pt.items() if t % 2 == k) for k in (0, 1)]
    for m in range(m_lo, m_hi + 1):
        pm = norm_cdf(m + 0.5, mu_m, margin_sd) - norm_cdf(m - 0.5, mu_m, margin_sd)
        for t, p in pt.items():
            if (t + m) % 2:
                continue  # parity: home = (t+m)/2 must be an integer
            h, a = (t + m) // 2, (t - m) // 2
            dist[(h, a)] = dist.get((h, a), 0) + pm * p / parity_mass[t % 2]
    home_win = norm_cdf(mu_m / margin_sd)
    for (h, a), p in list(dist.items()):
        if h == a:
            del dist[(h, a)]
            dist[(h + 1, a)] = dist.get((h + 1, a), 0) + p * home_win
            dist[(h, a + 1)] = dist.get((h, a + 1), 0) + p * (1 - home_win)
    norm = sum(dist.values())
    return Outcomes({k: v / norm for k, v in dist.items()})

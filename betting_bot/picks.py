"""Turn model probabilities + market prices into graded picks."""
from collections import defaultdict

MODEL_WEIGHT = 0.4        # markets are sharp: blend model 40 / market 60
MIN_EV = 0.03             # need +3% expected value
MIN_PRICE, MAX_PRICE = 1.40, 4.00
MAX_DISAGREE = 0.15       # bigger gap = probably missing news (injury/goalie)
KELLY_FRACTION = 0.25
MAX_STAKE = 0.02          # never more than 2% of bankroll on one bet

PAIR = {"home": "away", "away": "home", "over": "under", "under": "over"}


def model_prob(outcomes, q, three_way=None):
    """(win, push, loss) for a quote from the model."""
    m = q["market"]
    if m == "moneyline":
        p = outcomes.moneyline()[q["side"]]
        return p, 0.0, 1 - p
    if m == "handicap":
        return outcomes.handicap(q["side"], q["point"])
    if m == "total":
        return outcomes.total(q["side"], q["point"])
    if m == "3way" and three_way:
        p = three_way[q["side"]]
        return p, 0.0, 1 - p
    return None


def _pair_key(q):
    if q["market"] == "handicap":
        return (q["book"], "handicap", abs(q["point"]))
    if q["market"] == "total":
        return (q["book"], "total", q["point"])
    return (q["book"], q["market"], None)


def market_fair(quotes):
    """No-vig probability per (market, side, point), averaged across books."""
    groups = defaultdict(list)
    for q in quotes:
        groups[_pair_key(q)].append(q)
    fair = defaultdict(list)
    for key, qs in groups.items():
        if key[1] == "handicap":
            # make sure the two sides are opposite lines (home -x / away +x)
            sides = {q["side"]: q for q in qs}
            if set(sides) != {"home", "away"} or abs(sides["home"]["point"] + sides["away"]["point"]) > 1e-9:
                continue
            qs = list(sides.values())
        need = 3 if key[1] == "3way" else 2
        if len({q["side"] for q in qs}) != need or len(qs) != need:
            continue
        inv = [1 / q["price"] for q in qs]
        s = sum(inv)
        for q, i in zip(qs, inv):
            fair[(q["market"], q["side"], q["point"])].append(i / s)
    return {k: sum(v) / len(v) for k, v in fair.items()}


def grade(game, outcomes, three_way=None):
    """Return every priced line with EV, sorted best first."""
    fair = market_fair(game["quotes"])
    best = {}
    for q in game["quotes"]:
        k = (q["market"], q["side"], q["point"])
        if k not in best or q["price"] > best[k]["price"]:
            best[k] = q
    rows = []
    for k, q in best.items():
        mp = model_prob(outcomes, q, three_way)
        if mp is None:
            continue
        win, push, loss = mp
        mkt = fair.get(k)
        if mkt is not None:
            decided = max(win + loss, 1e-9)
            mkt_win = mkt * decided  # market prob excludes pushes
            p_win = MODEL_WEIGHT * win + (1 - MODEL_WEIGHT) * mkt_win
        else:
            mkt_win, p_win = None, win
        p_loss = max(0.0, 1 - push - p_win)
        b = q["price"] - 1
        ev = p_win * b - p_loss
        kelly = max(0.0, (b * p_win - p_loss) / b) * KELLY_FRACTION if b > 0 else 0.0
        rows.append({
            "market": q["market"], "side": q["side"], "point": q["point"],
            "price": q["price"], "book": q["book"],
            "model_p": win, "market_p": mkt_win, "push_p": push, "p": p_win,
            "ev": ev, "stake": min(kelly, MAX_STAKE),
            "disagree": abs(win - mkt_win) if mkt_win is not None else None,
        })
    rows.sort(key=lambda r: r["ev"], reverse=True)
    return rows


def select(rows, min_ev=MIN_EV):
    """Filter graded lines down to bettable picks (max one per market)."""
    picks, seen = [], set()
    for r in rows:
        if r["ev"] < min_ev or not (MIN_PRICE <= r["price"] <= MAX_PRICE):
            continue
        if r["market_p"] is None:
            continue  # no two-way market to sanity-check against
        if r["disagree"] is not None and r["disagree"] > MAX_DISAGREE:
            continue
        if r["market"] in seen:
            continue
        seen.add(r["market"])
        picks.append(r)
    return picks


def label(game, r):
    side = r["side"]
    if side in ("home", "away"):
        name = game[side]["abbrev"]
    else:
        name = side.capitalize()
    if r["market"] == "moneyline":
        return f"{name} ML"
    if r["market"] == "3way":
        return "Draw (60 min)" if side == "draw" else f"{name} (60 min)"
    if r["market"] == "handicap":
        return f"{name} {r['point']:+g}"
    return f"{name} {r['point']:g}"

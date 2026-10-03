"""Team-name normalisation so odds feeds can be matched to official games."""
import unicodedata

ALIASES = {
    # odds-feed spelling -> official nickname
    "blazers": "trail blazers",
    "la clippers": "clippers",
    "sixers": "76ers",
}


def norm(name):
    name = unicodedata.normalize("NFKD", name or "")
    name = "".join(c for c in name if not unicodedata.combining(c))
    return " ".join(name.lower().replace(".", "").split())


def same_team(feed_name, official_full, official_nick):
    """True when a feed name refers to the official team.

    Matches on the nickname (unique within a league) so 'LA Clippers',
    'Los Angeles Clippers' and 'Clippers' all resolve to the same club.
    """
    f = norm(feed_name)
    f = ALIASES.get(f, f)
    nick = norm(official_nick)
    return f == norm(official_full) or f == nick or f.endswith(" " + nick)

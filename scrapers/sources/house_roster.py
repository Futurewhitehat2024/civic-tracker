"""Match a House filing to a current representative's party.

The clerk's disclosure XML has a name and a state/district code, and no party.
The public unitedstates/congress-legislators roster supplies the party.
"""

import json
import logging
import re
from dataclasses import dataclass

log = logging.getLogger(__name__)

ROSTER_URL = (
    "https://unitedstates.github.io/congress-legislators/legislators-current.json"
)

_PARTY = {
    "democrat": "Democratic",
    "democratic": "Democratic",
    "republican": "Republican",
    "independent": "Independent",
}
_SUFFIXES = frozenset({"jr", "sr", "ii", "iii", "iv", "v"})
_TITLES = frozenset({"mr", "mrs", "ms", "miss", "hon", "dr"})
# Filing names use the legal given name. The roster often uses the short form.
_ALSO_CALLED = {
    "rick": ("richard",),
    "richard": ("rick",),
    "ro": ("rohit",),
    "rohit": ("ro",),
    "jim": ("james",),
    "james": ("jim", "j"),
    "j": ("james",),
    "bill": ("william",),
    "william": ("bill",),
    "bob": ("robert",),
    "robert": ("bob", "rob"),
}
_PUNCT = re.compile(r"[.'’,]")


@dataclass(frozen=True)
class Representative:
    party: str
    state: str
    district: int | None
    last: str
    firsts: frozenset[str]
    aliases: frozenset[str]


@dataclass(frozen=True)
class HouseRoster:
    members: tuple[Representative, ...]

    def party_for(self, member: str, state: str | None, district: int | None) -> str | None:
        if not state:
            log.info("house-ptr party unresolved for %s: no state", member)
            return None
        pool = [rep for rep in self.members if rep.state == state.upper()]
        if district is not None:
            in_district = [rep for rep in pool if rep.district == district]
            if in_district:
                pool = in_district
        named = [rep for rep in pool if _names_match(member, rep)]
        if len(named) == 1:
            return named[0].party
        if len(named) > 1:
            log.info(
                "house-ptr party unresolved for %s (%s-%s): %s matches",
                member,
                state,
                district if district is not None else "",
                len(named),
            )
            return None
        log.info(
            "house-ptr party unresolved for %s (%s-%s)",
            member,
            state,
            district if district is not None else "",
        )
        return None


def parse_roster(payload: str | bytes | list) -> HouseRoster:
    if isinstance(payload, list):
        raw = payload
    else:
        text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        loaded = json.loads(text)
        if not isinstance(loaded, list):
            raise ValueError("House roster was not a list")
        raw = loaded
    members: list[Representative] = []
    for person in raw:
        if not isinstance(person, dict):
            continue
        parsed = _representative(person)
        if parsed is not None:
            members.append(parsed)
    return HouseRoster(tuple(members))


def normalize_name(value: str) -> str:
    text = _PUNCT.sub("", value.lower().replace("-", " "))
    tokens = [token for token in text.split() if token and token not in _TITLES]
    while tokens and tokens[-1] in _SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def _representative(person: dict) -> Representative | None:
    terms = [
        term
        for term in person.get("terms") or []
        if isinstance(term, dict) and term.get("type") == "rep"
    ]
    if not terms:
        return None
    term = terms[-1]
    state = term.get("state")
    party = _PARTY.get(str(term.get("party") or "").strip().lower())
    if not isinstance(state, str) or not party:
        return None
    district = term.get("district")
    if isinstance(district, str) and district.isdigit():
        district = int(district)
    if not isinstance(district, int):
        district = None
    name = person.get("name") if isinstance(person.get("name"), dict) else {}
    first = normalize_name(str(name.get("first") or ""))
    last = normalize_name(str(name.get("last") or ""))
    if not first or not last:
        return None
    nickname = normalize_name(str(name.get("nickname") or ""))
    middle = normalize_name(str(name.get("middle") or ""))
    official = normalize_name(str(name.get("official_full") or ""))
    aliases = {f"{first} {last}"}
    if official:
        aliases.add(official)
    if middle:
        aliases.add(f"{first} {middle} {last}")
    if nickname:
        aliases.add(f"{nickname} {last}")
    given = {token for token in (first, nickname, middle) if token and len(token) > 1}
    given.add(first)
    for token in list(given):
        given.update(_ALSO_CALLED.get(token, ()))
    firsts = frozenset(token for token in given if token)
    return Representative(party, state.upper(), district, last, firsts, frozenset(aliases))


def _names_match(member: str, rep: Representative) -> bool:
    filing = normalize_name(member)
    if not filing:
        return False
    if filing in rep.aliases:
        return True
    tokens = filing.split()
    if len(tokens) >= 3 and f"{tokens[-2]} {tokens[-1]}" == rep.last:
        given = tokens[:-2]
    elif tokens and tokens[-1] == rep.last:
        given = tokens[:-1]
    else:
        return False
    return any(token in rep.firsts for token in given)

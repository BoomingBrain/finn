"""Sorts announcements into the reference categories: free regex rules first, the bulk LLM only for
leftovers. Then each category maps to a tier: critical, notable or routine."""
import re

from pydantic import BaseModel

from finn.llm import LLM
from finn.models import CATEGORIES, Announcement, Category, Tier

TIER_BY_CATEGORY: dict[str, Tier] = {
    "results": "critical", "M&A": "critical", "management_change": "critical", "fund_raise": "critical",
    "litigation": "critical", "pledging": "critical",
    "credit_rating": "notable", "capex": "notable", "insider_trading": "notable", "dividend": "notable",
    "bonus_split": "notable", "press_release": "notable",
    "earnings_call": "routine", "investor_meetings": "routine", "postal_ballot": "routine", "agm_egm": "routine",
    "unclassified": "routine",
}

# Ordered: the first match wins. Specific and routine patterns come before broad ones, e.g. ESOP allotments
# before fund raising, trading-window closures before insider trading, order wins before litigation.
_RULES: list[tuple[Category, str]] = [
    ("unclassified", r"\besops?\b|\besos\b|\besps\b|employee stock|grant of .{0,20}options|reg(ulation)? ?74\b"
                     r"|depositories and participants|trading window|special window|physical shares"
                     r"|loss of share certificate|duplicate share|\biepf\b|unclaimed|unpaid dividend|\bbrsr\b"
                     r"|business responsibility|\besg\b|compliance certificate|investor grievance|reg(ulation)? ?40\b"
                     r"|appointment of (the )?(statutory |secretarial |internal |cost )?auditors?"
                     r"|giving of guarantees?|guarantees? or indemnity|becoming a surety"),
    ("pledging", r"pledge|encumbrance|regulation 31\b"),
    ("insider_trading", r"regulation 7 ?\(2\)|reg 7 ?\(2\)|regulation 29\b|\bsast\b|insider trading disclosure"
                        r"|(promoter|director|insider)s?.{0,30}(bought|sold|acquired|disposed|purchase|sale) of shares"
                        r"|acquisition of shares by (the )?(promoter|director)"),
    ("postal_ballot", r"postal ballot"),
    ("agm_egm", r"annual general meeting|\bagm\b|\begm\b|extra-?ordinary general meeting|scrutini[sz]er"),
    ("investor_meetings", r"schedule of (analysts? |investors? )?meet|investor conference"),
    ("results", r"financial results?|results? (for|of) the (quarter|period|half|year)|quarter(ly)? results"
                r"|report of (the )?auditors? on (the )?financial|auditors?'? report on (the )?(financial|results)"
                r"|results? deck|shareholders? letter|(?=.*newspaper)(?=.*(financial|result))"
                r"|(?=.*presentation)(?=.*(earning|result|financial|\bq[1-4]\b|\bh[12]\b))"),
    ("earnings_call", r"transcript|link of recording|recording of|audio recording|earnings? ?(conference )?call|concall"),
    ("dividend", r"dividend"),
    ("bonus_split", r"bonus (issue|shares)|stock split|sub-?division|split of (equity )?shares"),
    ("credit_rating", r"credit rating|rating (agency|action|reaffirm|upgrade|downgrade)"
                      r"|\b(icra|crisil|care ratings|india ratings|fitch|moody)"),
    ("management_change", r"(appoint|resign|retire|cessation|re-?designat).{0,80}(director|officer|\bceo\b|\bcfo\b"
                          r"|\bcoo\b|\bmd\b|managing|chairman|chairperson|president|\bkmp\b|key managerial"
                          r"|company secretary|compliance officer)"
                          r"|change in (the )?(managing director|chief|director|management|\bkmp\b|key managerial)"
                          r"|(managing director|chief \w+ officer|\bceo\b|\bcfo\b).{0,40}(appoint|resign|retire|step)"
                          r"|\bappt\b"),
    ("fund_raise", r"qip|qualified institution|rights issue|preferential (issue|allotment)|buy-?back"
                   r"|commercial paper|non[- ]convertible|\bncds?\b|\bbonds?\b|fund ?rais|raising of funds"
                   r"|issue of securities"
                   r"|private placement|\bwarrants\b"),
    ("M&A", r"acqui(re|sition)|amalgamation|merger|demerger|joint venture|scheme of arrangement|divest"
            r"|stake (sale|in)|wholly[- ]owned subsidiary|incorporation of (a )?(new )?subsidiary|takeover"),
    ("capex", r"capacity expansion|new (plant|facility|manufacturing unit)|\bcapex\b|capital expenditure"
              r"|commission(ed|ing) of|greenfield|brownfield"),
    ("press_release", r"bagging/receiving of orders|\b(bags|secures|wins|receives|bagged|secured|won|received)\b.{0,40}\borders?\b"
                      r"|order (win|inflow|received)"),
    ("litigation", r"action\(s\) (taken|initiated) or orders passed|penalt|show[- ]cause|demand (notice|order)|tax demand"
                   r"|litigation|\bcourt\b|tribunal|\bnclt\b|\bnclat\b|insolvency|arbitration|regulatory action"
                   r"|warning letter|search (and|&) seizure|summons"),
    ("press_release", r"press release|media (release|statement)|\bpr\b"),
    ("investor_meetings", r"analysts?(\(s\))?/(institutional )?investors?(\(s\))? meet|analysts? meet|investors? meet|roadshow|non-deal"),
    ("unclassified", r"newspaper|clipping|advertisement|informed the exchange about general updates"),
]
_COMPILED = [(category, re.compile(pattern, re.I)) for category, pattern in _RULES]

# Announcements about a future announcement ("results on Oct 23", "board meeting scheduled to consider results")
# keep their category but are routine: the event itself is what matters.
_NOTICE = re.compile(
    r"intimation of (the )?board meeting|(board|meeting of the board)[^.]{0,80}(scheduled|to be held|will be held)"
    r"|to announce [^.]{0,60}results|prior intimation|will (hold|host) an? (analyst|investor|earnings)", re.I)


def _text(subject: str, raw_category: str | None, attachment: str | None) -> str:
    filename = (attachment or "").rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return " | ".join([raw_category or "", subject, re.sub(r"[_\-]+", " ", filename)])


def classify_rule(subject: str, raw_category: str | None = None, attachment: str | None = None) -> Category | None:
    text = _text(subject, raw_category, attachment)
    return next((category for category, rx in _COMPILED if rx.search(text)), None)


def tier_for(category: Category, subject: str) -> Tier:
    return "routine" if _NOTICE.search(subject) else TIER_BY_CATEGORY[category]


class _Label(BaseModel):
    i: int
    category: str


class _Labels(BaseModel):
    labels: list[_Label]


_SYSTEM = """You classify Indian stock-exchange announcements into exactly one category:
results (quarterly/annual results, results board meetings, results decks), M&A (acquisitions, mergers, demergers,
JVs, subsidiary stake purchases or sales, subsidiary listings), fund_raise (QIP, rights, preferential, buyback, debt),
management_change (CEO/CFO/MD/director joining, leaving or retiring), litigation (lawsuits, regulatory orders, fines,
insolvency), insider_trading (promoter/insider buying or selling), earnings_call (call notice, transcript, recording),
investor_meetings (meetings with investors, conferences), credit_rating, dividend, bonus_split, capex (new plant or
capacity), press_release (order wins, products, partnerships, clarifications, general company news), postal_ballot,
agm_egm, pledging (promoter share pledges), unclassified (routine paperwork that does not move the stock).
Reply with ONLY JSON: {"labels": [{"i": <index>, "category": "<category>"}]}"""


def classify(items: list[Announcement], llm: LLM, batch: int = 25) -> dict[str, Category]:
    """Category per announcement id. Rules first; one bulk-tier LLM call per `batch` leftovers."""
    out: dict[str, Category] = {}
    leftovers: list[Announcement] = []
    for a in items:
        category = classify_rule(a.subject, a.raw_category, a.attachment_url)
        if category:
            out[a.id] = category
        else:
            leftovers.append(a)
    for start in range(0, len(leftovers), batch):
        chunk = leftovers[start:start + batch]
        lines = "\n".join(f"{i}. [{a.raw_category or ''}] {a.subject} (file: {(a.attachment_url or '').rsplit('/', 1)[-1]})"
                          for i, a in enumerate(chunk))
        labels = llm.complete_json("bulk", _SYSTEM, lines, _Labels, max_tokens=50 + 20 * len(chunk))
        by_index = {label.i: label.category for label in labels.labels}
        for i, a in enumerate(chunk):
            category = by_index.get(i)
            out[a.id] = category if category in CATEGORIES else "unclassified"
    return out

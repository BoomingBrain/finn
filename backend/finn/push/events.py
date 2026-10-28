"""Display helpers for events (clustering lives in cluster.py)."""
import re


_BOILERPLATE = re.compile(r"^.*?\bhas (informed|submitted to) the exchange\b(\s+(that|about|regarding))?[\s,:-]*",
                          re.I)


_REG30 = re.compile(r"^(disclosure|intimation)s? under regulation 30\b.*?regulations?,? 2015\s*[-–—:]+\s*", re.I)


def headline(subject: str, fallback: str | None = None) -> str:
    """'Infosys Limited has informed the Exchange regarding 'X'.' -> 'X'."""
    text = _BOILERPLATE.sub("", subject).strip().strip("'\"‘’“” .").strip()
    text = _REG30.sub("", text)
    text = text or (fallback or subject)
    return text[:1].upper() + text[1:]


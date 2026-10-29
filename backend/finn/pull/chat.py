"""The Chat tab's answer step: the fast model answers only from retrieved report passages, and every sentence must
cite one of them or it is dropped (the same guard the dossiers use)."""
from datetime import date

from pydantic import BaseModel

from finn.llm import LLM
from finn.pull.sections import GROUNDING_RULES, Point, drop_uncited
from finn.rag import Passage

NOT_COVERED = "The reports don't cover that."
# Best cosine below this, with no company named, means the question isn't about anything researched. Measured on
# 29 Oct: relevant questions 0.33-0.59, off-topic ones (weather, cricket, poems, bitcoin) 0.10-0.20.
RELEVANCE_MIN = 0.25
PENDING = "Research pending for {name}."
MAX_POINTS = 5

_PROMPT = """Answer the investor's question in at most 5 short sentences, using only the passages below from FINN's
research reports. Cite passage ids exactly as given. Plain language, numbers as written in the passages.
If no passage answers the question, return {{"points": []}}; never answer with unrelated facts.
Return JSON: {{"points": [{{"text": "...", "source_ids": ["SYMBOL#n", ...]}}]}}

Question: {question}

{passages}"""


class _Answer(BaseModel):
    points: list[Point] = []


def answer(question: str, passages: list[Passage], llm: LLM) -> list[Point]:
    """At most MAX_POINTS cited points; an empty list means the passages don't answer the question."""
    if not passages:
        return []
    blocks = "\n".join(f"[{p.id}] {p.text}" for p in passages)
    reply = llm.complete_json("bulk", GROUNDING_RULES, _PROMPT.format(question=question, passages=blocks), _Answer,
                              max_tokens=900)
    for p in reply.points:
        p.source_ids = [i.strip(" []") for i in p.source_ids]
    return drop_uncited(reply.points, {p.id for p in passages}, key=lambda p: p.source_ids)[:MAX_POINTS]


def chip_label(source_id: str) -> str:
    """The same short labels the web app uses: "Aug '26 call p12", "AR p73", "Screener"."""
    if source_id == "SCR":
        return "Screener"
    kind, doc, page = (source_id.split(":") + ["", ""])[:3]
    if kind == "T":
        d = date.fromisoformat(doc)
        return f"{d.strftime('%b')} '{d.year % 100:02d} call {page}".strip()
    if kind == "AR":
        return f"AR {page}".strip()
    return source_id

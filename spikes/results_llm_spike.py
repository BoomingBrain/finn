"""Throwaway spike: which NVIDIA-hosted pipeline extracts the headline results numbers correctly?
Scores three pipelines against the hand-checked values in docs/spikes.md:

  A  parse+text : page image -> nvidia/nemotron-parse-2.0 (table markdown) -> lightning -> JSON
  B  vision     : page image -> nvidia/nemotron-3.5-super-vl-120b-a12b -> JSON
  C  ocr+text   : PDF text layer (OCR) -> lightning -> JSON            (baseline)

Needs NVIDIA_API_KEY in ../.env. Usage: uv run python results_llm_spike.py
"""
import base64
import json
import re
import time
from pathlib import Path

import pymupdf

from nv import chat

PARSE = "nvidia/nemotron-parse-2.0"
VISION = "nvidia/nemotron-3.5-super-vl-120b-a12b"
TEXT = "nvidia/nemotron-3.5-lightning-30b-a3b"
NO_THINK = {"chat_template_kwargs": {"enable_thinking": False}}

FIX = Path(__file__).resolve().parent.parent / "backend/tests/fixtures/results"
# (file, 0-based page index of the results statement, hand-checked values in ₹ crore: current, prev_q, year_ago)
CASES = {
    "INFY": ("INFY_q2fy27_statements.pdf", 4, {
        "revenue": [49244, 48211, 44490], "other_income": [848, 984, 982],
        "finance_costs": [115, 119, 106], "depreciation": [1359, 1246, 1182],
        "pbt": [11063, 11028, 10229], "pat": [7838, 7775, 7375]}),
    "HDFCBANK": ("HDFCBANK_q2fy27.pdf", 1, {
        "interest_earned": [83426.60, 79362.78, 76690.70], "interest_expended": [48807.42, 45828.83, 45139.20],
        "ppop": [29483.42, 28168.06, 27923.60], "pbt": [25909.80, 25108.30, 24423.07],
        "pat": [19509.96, 19059.72, 18641.28]}),
}
PROMPT = """Below is a quarterly results statement of an Indian listed company.
Return ONLY JSON: {"unit": "crores|lakhs|millions|thousands|rupees", "columns": [
  {"header": "<column header text>", "period_months": 3|6|12, "period_end": "YYYY-MM-DD",
   "revenue": n|null, "other_income": n|null, "finance_costs": n|null, "depreciation": n|null,
   "interest_earned": n|null, "interest_expended": n|null, "ppop": n|null, "pbt": n|null, "pat": n|null}]}
Include every numeric column, left to right. Copy numbers exactly as printed (no unit conversion);
parentheses mean negative. revenue = revenue from operations (non-banks). ppop = operating profit before
provisions and contingencies (banks only). pat = profit for the period (total, before minority split)."""


def page_png(doc, page: int) -> bytes:
    rect = doc[page].rect
    zoom = min(1664 / rect.width, 2048 / rect.height)  # nemotron-parse's recommended max resolution
    return doc[page].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes("png")


def image_part(png: bytes) -> dict:
    return {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode()}}


def content(resp: dict) -> str:
    return resp["choices"][0]["message"].get("content") or ""


def to_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text[text.find("{"): text.rfind("}") + 1])


def pipeline_a(doc, page):
    md = content(chat(PARSE, [{"role": "user", "content": [{"type": "text", "text": "</s><s><output_markdown>"},
                                                           image_part(page_png(doc, page))]}],
                      max_tokens=3500, temperature=0, top_p=1))
    md = re.sub(r"<x_[\d.]+><y_[\d.]+>|<class_[\w-]+>", "", md)  # drop bbox/class tokens
    return to_json(content(chat(TEXT, [{"role": "user", "content": PROMPT + "\n\nSTATEMENT:\n" + md}],
                                max_tokens=3000, temperature=0, **NO_THINK)))


def pipeline_b(doc, page):
    return to_json(content(chat(VISION, [{"role": "user", "content": [image_part(page_png(doc, page)),
                                                                     {"type": "text", "text": PROMPT}]}],
                                max_tokens=4000, temperature=0, **NO_THINK)))


def pipeline_c(doc, page):
    return to_json(content(chat(TEXT, [{"role": "user", "content": PROMPT + "\n\nSTATEMENT (OCR text):\n" + doc[page].get_text()}],
                                max_tokens=3000, temperature=0, **NO_THINK)))


def score(cols: list[dict], gold: dict) -> tuple[int, int, list[str]]:
    quarters = [c for c in cols if c.get("period_months") == 3][:3]
    ok, total, misses = 0, 0, []
    for field, expected in gold.items():
        for i, exp in enumerate(expected):
            total += 1
            got = quarters[i].get(field) if i < len(quarters) else None
            try:
                good = got is not None and abs(float(str(got).replace(",", "")) - exp) <= abs(exp) * 0.005
            except ValueError:
                good = False
            if good:
                ok += 1
            else:
                misses.append(f"{field}[{i}] expected {exp} got {got}")
    return ok, total, misses


def main():
    summary = {}
    for sym, (fname, page, gold) in CASES.items():
        doc = pymupdf.open(FIX / fname)
        for name, fn in [("A parse+text", pipeline_a), ("B vision", pipeline_b), ("C ocr+text", pipeline_c)]:
            t = time.time()
            try:
                data = fn(doc, page)
                ok, total, misses = score(data.get("columns", []), gold)
                line = f"{ok}/{total}"
            except Exception as e:  # noqa: BLE001
                ok, total, misses, line = 0, sum(len(v) for v in gold.values()), [f"{type(e).__name__}: {str(e)[:200]}"], "ERROR"
            summary.setdefault(name, [0, 0])
            summary[name][0] += ok
            summary[name][1] += total
            print(f"{sym:9} {name:13} {line:7} fields  {time.time() - t:5.1f}s")
            for m in misses[:5]:
                print("              miss:", m)
    print("\nTOTAL")
    for name, (ok, total) in summary.items():
        print(f"  {name:13} {ok}/{total} = {100 * ok / total:.0f}%")


if __name__ == "__main__":
    main()

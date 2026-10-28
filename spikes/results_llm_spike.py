"""Throwaway spike: does Haiku extract the headline results numbers correctly, and is the page IMAGE
or the OCR TEXT layer the better input? Scores both against hand-checked values (docs/spikes.md).

Needs ANTHROPIC_API_KEY. Usage: uv run python results_llm_spike.py
"""
import base64
import json
import re
from pathlib import Path

import anthropic
import pymupdf

MODEL = "claude-haiku-5-5"
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
PROMPT = """This is a page from an Indian listed company's quarterly results filing.
Return ONLY JSON: {"unit": "crores|lakhs|millions|thousands|rupees", "columns": [
  {"header": "<column header text as printed>", "period_months": 3|6|12, "period_end": "YYYY-MM-DD",
   "revenue": n|null, "other_income": n|null, "finance_costs": n|null, "depreciation": n|null,
   "interest_earned": n|null, "interest_expended": n|null, "ppop": n|null, "pbt": n|null, "pat": n|null}]}
Include every numeric column, left to right. Copy numbers exactly as printed (no unit conversion);
parentheses mean negative. ppop = operating profit before provisions and contingencies (banks only).
pat = profit for the period (total, before minority split)."""


def ask(client, content) -> dict:
    msg = client.messages.create(model=MODEL, max_tokens=3000, messages=[{"role": "user", "content": content}])
    text = msg.content[0].text
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M)
    return {"data": json.loads(text), "in": msg.usage.input_tokens, "out": msg.usage.output_tokens}


def score(cols: list[dict], gold: dict) -> tuple[int, int, list[str]]:
    quarters = [c for c in cols if c.get("period_months") == 3][:3]
    ok, total, misses = 0, 0, []
    for field, expected in gold.items():
        for i, exp in enumerate(expected):
            total += 1
            got = quarters[i].get(field) if i < len(quarters) else None
            if got is not None and abs(float(got) - exp) <= abs(exp) * 0.005:
                ok += 1
            else:
                misses.append(f"{field}[{i}] expected {exp} got {got}")
    return ok, total, misses


def main():
    client = anthropic.Anthropic()
    for sym, (fname, page, gold) in CASES.items():
        doc = pymupdf.open(FIX / fname)
        png = doc[page].get_pixmap(dpi=150).tobytes("png")
        image = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                              "data": base64.b64encode(png).decode()}},
                 {"type": "text", "text": PROMPT}]
        text = [{"type": "text", "text": PROMPT + "\n\nPAGE TEXT (OCR):\n" + doc[page].get_text()}]
        for mode, content in [("image", image), ("ocr_text", text)]:
            r = ask(client, content)
            ok, total, misses = score(r["data"]["columns"], gold)
            print(f"{sym:9} {mode:9} {ok}/{total} fields correct  tokens in/out {r['in']}/{r['out']}  unit={r['data'].get('unit')}")
            for m in misses[:6]:
                print("           miss:", m)


if __name__ == "__main__":
    main()

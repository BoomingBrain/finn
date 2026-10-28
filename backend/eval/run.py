"""Scores extraction against the hand-checked gold sets and prints markdown tables (`make eval`).

Results: the same pipeline as ingest (page selection on the PDF text, vision read, arithmetic re-read, compute);
a field is correct within 0.5%. Transcripts: `extract_targets`; a target matches on metric + period + value within
0.5. Model calls are cached, so a re-run is free."""
from pathlib import Path

import yaml

from finn.llm import LLM
from finn.portfolio import load_portfolio
from finn.pull.guidance import extract_targets
from finn.push.results import compute_results, extract_results, select_statement_page
from finn.sources.documents import DocText, fetch_pdf, fetch_pdf_text, pdf_text
from finn.sources.screener import fetch_company

HERE = Path(__file__).parent
BACKEND = HERE.parent


def _pdf(source: str) -> Path:
    return fetch_pdf(source) if source.startswith("http") else BACKEND / source


def results_eval(llm: LLM) -> tuple[str, int, int]:
    portfolio = load_portfolio()
    lines = ["| Filing | Correct | Misses |", "|---|---|---|"]
    total = correct = 0
    for doc in yaml.safe_load((HERE / "results_gold.yaml").read_text()):
        path = _pdf(doc["source"])
        holding = portfolio.holding(doc["name"].split()[0])
        page = select_statement_page(DocText(url=doc["source"], pages=pdf_text(path)))
        card = compute_results(extract_results(path, page, llm), holding.sector if holding else None) \
            if page is not None else None
        misses, n = [], 0
        for metric, gold in doc["metrics"].items():
            row = card.metrics.get(metric) if card and card.status == "ok" else None
            got = [row.current, row.prev_q, row.year_ago] if row else [None] * 3
            for col, (g, v) in enumerate(zip(gold, got)):
                total += 1
                if v is not None and abs(v - g) <= 0.005 * abs(g):
                    n += 1
                else:
                    misses.append(f"{metric}[{col}] {v if v is None else round(v, 2)} vs {g}")
        correct += n
        status = "" if card and card.status == "ok" else f" (card {card.status if card else 'no page'})"
        lines.append(f"| {doc['name']} | {n}/{3 * len(doc['metrics'])}{status} | {'; '.join(misses) or '—'} |")
    lines.append(f"| **Total** | **{correct}/{total} ({100 * correct / total:.0f}%)** | |")
    return "\n".join(lines), correct, total


def _matches(t, g) -> bool:
    return t.metric == g["metric"] and abs(t.value - g["value"]) <= 0.5 and ("period" not in g or
                                                                           t.period.upper() == g["period"])


def transcripts_eval(llm: LLM) -> str:
    lines = ["| Call | Gold targets | Found | Extracted | False positives |", "|---|---|---|---|---|"]
    tp = gold_n = fp = 0
    for call in yaml.safe_load((HERE / "transcripts_gold.yaml").read_text()):
        link = next(t for t in fetch_company(call["symbol"]).transcripts if t.date == call["said_on"])
        targets = extract_targets(fetch_pdf_text(link.url), link.date, llm)
        found = sum(any(_matches(t, g) for t in targets) for g in call["targets"])
        extra = [t for t in targets if not any(_matches(t, g) for g in call["targets"] + call["acceptable"])]
        tp, gold_n, fp = tp + found, gold_n + len(call["targets"]), fp + len(extra)
        detail = "; ".join(f"{t.metric} {t.value:g} {t.period}" for t in extra) or "—"
        lines.append(f"| {call['name']} | {len(call['targets'])} | {found} | {len(targets)} | {len(extra)}: {detail} |")
    precision = tp / (tp + fp) if tp + fp else 1.0
    lines.append(f"| **Total** | {gold_n} | recall **{tp}/{gold_n}** | | precision **{precision:.0%}** |")
    return "\n".join(lines)


def main():
    llm = LLM()
    table, _, _ = results_eval(llm)
    print("### Results extraction (field accuracy, within 0.5%)\n")
    print(table)
    print("\n### Guidance extraction (Promised vs Delivered)\n")
    print(transcripts_eval(llm))


if __name__ == "__main__":
    main()

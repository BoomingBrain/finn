from datetime import date
from pathlib import Path

import pytest

from finn.llm import LLM
from finn.push.results import (RawColumn, RawResults, check_arithmetic, compute_results, extract_results,
                               select_quarter_columns, select_statement_page)
from finn.sources.documents import DocText, pdf_text
from tests.fakes import FakeCompleter

FIXTURES = Path(__file__).parent / "fixtures" / "results"


def col(months, end, header="", **values):
    return RawColumn(header=header, period_months=months, period_end=end, **values)


def corporate(cur, prev, ya, unit="crores", **extra):
    """Columns from (revenue, other_income, finance_costs, depreciation, pbt, pat) tuples."""
    keys = ["revenue", "other_income", "finance_costs", "depreciation", "pbt", "pat"]
    cols = [col(3, end, **dict(zip(keys, vals))) for end, vals in
            [(date(2026, 9, 30), cur), (date(2026, 6, 30), prev), (date(2025, 9, 30), ya)]]
    return RawResults(statement_type="corporate", basis="consolidated", unit=unit, columns=cols, **extra)


def test_lakhs_normalised():
    card = compute_results(corporate((1_250_000, 0, 0, 0, 100, 80), (1_000_000, 0, 0, 0, 90, 70),
                                     (900_000, 0, 0, 0, 80, 60), unit="lakhs"))
    assert card.status == "ok"
    assert card.metrics["Revenue"].current == 12500.0


def test_ebitda_formula():
    card = compute_results(corporate((1000, 5, 10, 20, 100, 70), (1000, 5, 10, 20, 100, 70), (1000, 5, 10, 20, 100, 70)))
    assert card.metrics["EBITDA"].current == 125.0
    assert list(card.metrics) == ["Revenue", "EBITDA", "PBT", "PAT"]


def test_qoq_yoy_pct():
    card = compute_results(corporate((110, 0, 0, 0, 20, 10), (100, 0, 0, 0, 20, 10), (88, 0, 0, 0, 20, 10)))
    assert card.metrics["Revenue"].qoq_pct == 10.0
    assert card.metrics["Revenue"].yoy_pct == 25.0


def test_zero_base_pct_is_none():
    card = compute_results(corporate((110, 0, 0, 0, 20, 10), (100, 0, 0, 0, 0, 0), (88, 0, 0, 0, 20, 10)))
    assert card.metrics["PAT"].qoq_pct is None
    assert card.metrics["PAT"].yoy_pct == 0.0


def test_unreadable_when_pat_missing():
    card = compute_results(corporate((110, 0, 0, 0, 20, None), (100, 0, 0, 0, 20, 10), (88, 0, 0, 0, 20, 10)))
    assert card.status == "unreadable" and card.metrics == {}


def test_unreadable_when_pat_exceeds_revenue():
    card = compute_results(corporate((110, 0, 0, 0, 20, 500), (100, 0, 0, 0, 20, 10), (88, 0, 0, 0, 20, 10)))
    assert card.status == "unreadable" and card.metrics == {}


def test_q2_filing_picks_quarter_columns():
    cols = [col(3, date(2026, 9, 30), "a"), col(3, date(2026, 6, 30), "b"), col(3, date(2025, 9, 30), "c"),
            col(6, date(2026, 9, 30), "d"), col(6, date(2025, 9, 30), "e"), col(12, date(2026, 3, 31), "f")]
    assert [c.header for c in select_quarter_columns(cols)] == ["a", "b", "c"]


def test_q4_filing_picks_quarter_columns():
    cols = [col(3, date(2027, 3, 31), "a"), col(3, date(2026, 12, 31), "b"), col(3, date(2026, 3, 31), "c"),
            col(12, date(2027, 3, 31), "d"), col(12, date(2026, 3, 31), "e")]
    assert [c.header for c in select_quarter_columns(cols)] == ["a", "b", "c"]


def test_period_inferred_from_header():
    cols = [col(None, date(2026, 9, 30), "Six months ended 30.09.2026"), col(3, date(2026, 9, 30), "a"),
            col(3, date(2026, 6, 30), "b"), col(3, date(2025, 9, 30), "c")]
    assert [c.header for c in select_quarter_columns(cols)] == ["a", "b", "c"]


def test_scrambled_dates_fall_back_to_sebi_column_order():
    # Task 0: HDFCBANK's OCR scrambled the header dates; SEBI's standard order is current, previous, year-ago.
    cols = [col(3, None, "Quarter ended 30.09.2026"), col(3, date(2026, 9, 30), "Quarter ended 39.09.2026"),
            col(3, date(2026, 3, 31), "Quarter ended 30.09.2025"), col(6, date(2026, 9, 30), "Half year")]
    assert [c.header for c in select_quarter_columns(cols)] == [
        "Quarter ended 30.09.2026", "Quarter ended 39.09.2026", "Quarter ended 30.09.2025"]


def test_no_quarter_triplet_is_unreadable():
    raw = RawResults(statement_type="corporate", basis="consolidated", unit="crores",
                     columns=[col(3, date(2026, 9, 30), revenue=1, pbt=1, pat=1), col(6, date(2026, 9, 30))])
    assert select_quarter_columns(raw.columns) is None
    assert compute_results(raw).status == "unreadable"


def lender(statement_type, ppop=(30, 28, 27), **expense):
    rows = []
    for i, end in enumerate([date(2026, 9, 30), date(2026, 6, 30), date(2025, 9, 30)]):
        rows.append(col(3, end, interest_earned=100 - i, ppop=ppop[i] if ppop else None, pbt=25 - i, pat=19 - i,
                        **{k: v[i] for k, v in expense.items()}))
    return RawResults(statement_type=statement_type, basis="consolidated", unit="crores", columns=rows)


def test_bank_layout_nii():
    card = compute_results(lender("bank", interest_expended=(60, 60, 60)))
    assert card.layout == "lender"
    assert card.metrics["NII"].current == 40.0
    assert list(card.metrics) == ["NII", "PPOP", "PBT", "PAT"]
    assert card.not_applicable == ["EBITDA"]


def test_nbfc_layout_uses_finance_costs():
    card = compute_results(lender("nbfc", ppop=None, finance_costs=(55, 55, 55)))
    assert card.metrics["NII"].current == 45.0


def test_lender_without_ppop_omits_it():
    card = compute_results(lender("nbfc", ppop=None, finance_costs=(55, 55, 55)))
    assert list(card.metrics) == ["NII", "PBT", "PAT"]


def test_sector_override_forces_lender():
    raw = lender("corporate", interest_expended=(60, 60, 60))
    assert compute_results(raw, sector="Banks").layout == "lender"


# Arithmetic checks (Task 0: the vision model misread HDFCBANK Q2 PBT 25,909.80 as 26,909.80, deterministically)
def test_check_catches_misread_pbt():
    misread = col(3, date(2026, 9, 30), interest_earned=83426.60, other_income=13831.02, total_income=97257.62,
                  ppop=29483.42, provisions=3573.62, pbt=26909.80, tax=6399.84, pat=19509.96)
    assert set(check_arithmetic(misread, "lender")) == {"pbt", "pat"}
    assert check_arithmetic(misread.model_copy(update={"pbt": 25909.80}), "lender") == []


def test_check_allows_after_tax_items():
    # Consolidated statements often add share of associates after tax
    c = col(3, date(2026, 9, 30), revenue=1000, other_income=10, total_income=1010, pbt=200, tax=50,
            after_tax_items=12, pat=162)
    assert check_arithmetic(c, "corporate") == []


def test_check_sums_printed_tax_lines():
    # Task 4 smoke: INFY prints current 3,398 and deferred (173); the model added them wrongly (2,225).
    # The model now copies the lines and code adds them.
    c = col(3, date(2026, 9, 30), revenue=49244, other_income=848, total_income=50092, pbt=11063,
            tax=2225, tax_current=3398, tax_deferred=-173, pat=7838)
    assert check_arithmetic(c, "corporate") == []


def test_check_skips_missing_inputs():
    assert check_arithmetic(col(3, date(2026, 9, 30), revenue=1000, pbt=200, pat=150), "corporate") == []


def test_compute_refuses_numbers_that_dont_add_up():
    raw = corporate((1000, 5, 10, 20, 100, 70), (1000, 5, 10, 20, 100, 70), (1000, 5, 10, 20, 100, 70))
    raw.columns[0].tax = 10  # 100 - 10 != 70
    assert compute_results(raw).status == "unreadable"


def test_lenient_numbers_and_dates():
    c = RawColumn.model_validate({"header": "x", "period_months": 3, "period_end": "2026-09-39",
                                  "revenue": "49,244", "tax": "(173)", "pat": "-"})
    assert (c.period_end, c.revenue, c.tax, c.pat) == (None, 49244.0, -173.0, None)


GOOD = ('{"statement_type":"bank","basis":"consolidated","unit":"crores","columns":['
        '{"header":"Q","period_months":3,"period_end":"2026-09-30","ppop":10,"provisions":2,"pbt":8,"tax":2,"pat":6}]}')
BAD = GOOD.replace('"pbt":8', '"pbt":9')


def test_extract_rereads_at_200dpi_when_checks_fail(tmp_path):
    fake = FakeCompleter(responses=[BAD, GOOD])
    renders = []
    raw = extract_results(Path("doc.pdf"), 0, LLM(tmp_path / "c.sqlite", completer=fake),
                          render=lambda path, page, dpi=None: renders.append(dpi) or f"png{dpi}".encode())
    assert renders == [None, 200]
    assert "pbt" in fake.calls[1].user and fake.calls[1].model.endswith("super-vl-120b-a12b")
    assert raw.columns[0].pbt == 8


def test_extract_reads_once_when_checks_pass(tmp_path):
    fake = FakeCompleter(responses=[GOOD])
    raw = extract_results(Path("doc.pdf"), 0, LLM(tmp_path / "c.sqlite", completer=fake),
                          render=lambda path, page, dpi=None: b"png")
    assert len(fake.calls) == 1 and raw.columns[0].pbt == 8


# Page selection on the real Task 0 fixtures
def test_select_statement_page_infy():
    doc = DocText(url="infy", pages=pdf_text(FIXTURES / "INFY_q2fy27_statements.pdf"))
    assert select_statement_page(doc) == 4  # consolidated Ind AS statement, not the IFRS fact sheet


def test_select_statement_page_hdfcbank_prefers_consolidated():
    doc = DocText(url="hdfc", pages=pdf_text(FIXTURES / "HDFCBANK_q2fy27.pdf"))
    assert select_statement_page(doc) == 8


# Task 6 smoke: Bajaj Finance (NBFC) Q2 FY27, real extracted values
def test_nbfc_total_income_check_needs_total_revenue():
    # NBFC total income = all revenue from operations + other income; interest income alone never adds up
    c = col(3, date(2026, 9, 30), interest_earned=21936.39, other_income=29.45, total_income=24575.82, pbt=8537.20,
            tax=2170.63, pat=6366.57)
    assert check_arithmetic(c, "lender") == []


def test_check_accepts_printed_total_tax_when_components_are_incomplete():
    c = col(3, date(2026, 6, 30), interest_earned=20512.73, pbt=8149.00, tax_current=2442.67, tax=2068.40, pat=6080.60)
    assert check_arithmetic(c, "lender") == []


def test_check_still_fails_when_no_tax_reading_adds_up():
    c = col(3, date(2026, 6, 30), pbt=8149.00, tax_current=2442.67, tax=2000.00, pat=6080.60)
    assert check_arithmetic(c, "lender") == ["pat"]


def test_missing_ebitda_input_drops_only_ebitda():
    # Task 6 smoke: Persistent's finance-cost line wasn't read; Revenue/PBT/PAT were verified, so show them
    raw = corporate((46639.04, 244.45, None, 1666.73, 4536.84, 3515.14), (43032.27, 706.36, None, 1152.87, 6231.01, 4830.43),
                    (35807.20, 517.76, None, 1000.47, 6168.32, 4714.70), unit="millions")
    card = compute_results(raw)
    assert card.status == "ok"
    assert list(card.metrics) == ["Revenue", "PBT", "PAT"]
    assert card.missing == ["EBITDA"]
    assert card.metrics["Revenue"].current == 4663.9

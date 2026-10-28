import io
import zipfile
from datetime import datetime

import pymupdf
import pytest

from finn.models import IST, Announcement
from finn.push.enrich import clean_background, is_results_statement
from finn.push.events import headline
from finn.sources.documents import pdf_from_zip


def ann(subject, raw_category=None):
    return Announcement(id="x", symbol="X", company="X", filed_at=datetime(2026, 10, 15, tzinfo=IST), subject=subject,
                        body="", attachment_url="https://x/a.pdf", raw_category=raw_category, source="nse")


@pytest.mark.parametrize("subject, expected", [
    ("Infosys Limited has submitted to the Exchange, Financial Results for the quarter ended September 30, 2026", True),
    ("Outcome of the Board Meeting", True),  # Persistent Q2 FY27: the statement is inside; the PDF decides
    ("Infosys Limited has informed the Exchange about Copy of Newspaper Publication", False),
    ("Infosys Limited has informed the Exchange regarding 'Infosys to Announce Second Quarter Results on October 23, 2026'.", False),
    ("HDFC Bank Limited has informed the Exchange about Presentation", False),
    ("HDFC Bank Limited has informed the Exchange about Transcript", False),
])
def test_is_results_statement(subject, expected):
    assert is_results_statement(ann(subject)) is expected


@pytest.mark.parametrize("raw, expected", [
    ("Not Applicable", ""), ("N.A.", ""), ("NA", ""), ("-", ""), ("Nil", ""), ("None", ""),
    ("Holds a degree in engineering and has 30 years of experience.", "Holds a degree in engineering and has 30 years of experience."),
])
def test_clean_background(raw, expected):
    assert clean_background(raw) == expected


def test_headline_strips_regulation_30_boilerplate():
    subject = ("HDFC Bank Limited has informed the Exchange regarding disclosure under Regulation 30 and other applicable "
               "regulations of the SEBI (Listing Obligations and Disclosure Requirements) Regulations, 2015 - Change in "
               "Managing Director and Chief Executive Officer of the Bank")
    assert headline(subject) == "Change in Managing Director and Chief Executive Officer of the Bank"


def _pdf_bytes() -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Brief profile")
    return doc.tobytes()


def test_pdf_from_zip_returns_the_pdf_inside():
    # Task 6 smoke: SUNPHARMA/PERSISTENT/TRENT filed management changes as ..._KMP_Doc.zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("readme.txt", "x")
        z.writestr("KMP_Doc.pdf", _pdf_bytes())
    assert pdf_from_zip(buf.getvalue())[:4] == b"%PDF"


def test_pdf_from_zip_without_pdf_is_none():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("readme.txt", "x")
    assert pdf_from_zip(buf.getvalue()) is None
    assert pdf_from_zip(b"not a zip") is None

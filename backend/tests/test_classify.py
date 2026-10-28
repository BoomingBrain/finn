import pytest

from finn.models import CATEGORIES
from finn.push.classify import TIER_BY_CATEGORY, classify_rule, tier_for

ANALYST_MEET = "Analysts/Institutional Investor Meet/Con. Call Updates"


@pytest.mark.parametrize("subject, raw_category, attachment, expected", [
    # Plan cases
    ("Outcome of Board Meeting - Financial Results for the quarter ended September 30, 2026", None, None, "results"),
    ("Investor Presentation on Financial Results", None, None, "results"),
    ("Newspaper publication of financial results", None, None, "results"),
    ("Appointment of Mr. X as Chief Financial Officer", None, None, "management_change"),
    ("Resignation of Independent Director", None, None, "management_change"),
    ("Analysts/Institutional Investor Meet/Con. Call Updates", None, None, "investor_meetings"),
    ("Transcript of the Earnings Conference Call", None, None, "earnings_call"),
    ("Credit Rating - ICRA reaffirmed", None, None, "credit_rating"),
    ("Disclosure of creation of pledge by promoter", None, None, "pledging"),
    ("Acquisition of 51% stake in ABC Pvt Ltd", None, None, "M&A"),
    ("Allotment of shares under ESOP scheme", None, None, "unclassified"),
    ("Record date for interim dividend", None, None, "dividend"),
    # Real NSE filings (Task 0 fixtures): subject = attchmntText, raw_category = desc
    ("Infosys Limited has submitted to the Exchange, Financial Results for the quarter and half year ended "
     "September 30, 2026 and declaration of interim dividend", "Outcome of Board Meeting",
     "Infosys_23102026160704_BM_Outcome_Oct232026_1.pdf", "results"),
    ("Infosys Limited has informed the Exchange about Copy of Newspaper Publication", "Copy of Newspaper Publication",
     "Infosys_24102026194244_Financials_newspaper_ad_SE_filing.pdf", "results"),
    ("Infosys Limited has informed the Exchange regarding 'Report of auditors on financial statements for the "
     "quarter and half year ended September 30, 2026 withUDIN'.", "Updates", None, "results"),
    ("Infosys Limited has informed the Exchange that Record date for the purpose of Dividend  is 03-Nov-2026.",
     "Record Date", "Infosys_23102026160926_BM_Outcome_Oct232026_1.pdf", "dividend"),
    ("Infosys Limited has informed the Exchange regarding ' Investor Conference'.", "Updates", None, "investor_meetings"),
    ("Infosys Limited has informed the Exchange about Certificate under SEBI (Depositories and Participants) "
     "Regulations, 2018", "Certificate under SEBI (Depositories and Participants) Regulations, 2018", None, "unclassified"),
    ("HDFC Bank Limited has informed the Exchange regarding disclosure under Regulation 30 and other applicable "
     "regulations of the SEBI (Listing Obligations and Disclosure Requirements) Regulations, 2015 - Change in "
     "Managing Director and Chief Executive Officer of the Bank", "General Updates", None, "management_change"),
    ("HDFC Bank Limited has informed the Exchange about change in Management", "Change in Management",
     "HDFCBANK3_30092026183242_SE_Intimation-_CCO.pdf", "management_change"),
    ("HDFC Bank Limited has informed the Exchange regarding Grant of 1302379  Options.", "ESOP/ESOS/ESPS", None,
     "unclassified"),
    ("HDFC Bank Limited has informed the Exchange about Transcript", ANALYST_MEET, None, "earnings_call"),
    ("HDFC Bank Limited has informed the Exchange about Link of Recording", ANALYST_MEET, None, "earnings_call"),
    ("HDFC Bank Limited has informed the Exchange about Presentation", ANALYST_MEET,
     "HDFCBANK_17102026151509_SE_Intimation_earningcall_presentation17oct2026.pdf", "results"),
    ("HDFC Bank Limited has informed the Exchange about Schedule of meet", ANALYST_MEET,
     "HDFCBANK3_13102026161935_SE_Intimation_-_Earnings_call.pdf", "investor_meetings"),
    ("HDFC Bank Limited has informed the Exchange regarding Notice of Postal Ballot", "Shareholders meeting", None,
     "postal_ballot"),
    ("Newspaper publication regarding special window for transfer and dematerialization of physical shares of "
     "HDFC Bank Limited.", "General Updates", None, "unclassified"),
    ("Reliance Industries Limited has informed the Exchange regarding the Trading Window closure pursuant to SEBI "
     "(Prohibition of Insider Trading) Regulations, 2015", "Trading Window", None, "unclassified"),
    ("We wish to inform that the Company has today allotted 13,00,000 Unsecured, Redeemable, Non-Convertible "
     "Debentures (\"NCDs\") of the face value of Rs. 1,00,000 each (\"PPD Series R\"), issued on private placement "
     "basis.", "Allotment of Securities", None, "fund_raise"),
    ("Disclosure under Regulation 30 of the Securities and Exchange Board of India (Listing Obligations and "
     "Disclosure Requirements) Regulations, 2015 is attached.", "Action(s) taken or orders passed", None, "litigation"),
    ("Reliance Industries Limited has informed the Exchange about Credit Rating", "Credit Rating", None, "credit_rating"),
    ("Please find attached a media statement issued by the Company.", "Updates", None, "press_release"),
    # Order wins are news, not litigation
    ("Larsen & Toubro bags significant order for a metro rail project", "Updates", None, "press_release"),
    # Live NSE filings, 21-28 Oct 2026 (Task 3 smoke run): cases the first rule set or the LLM got wrong
    ("Larsen & Toubro Limited has informed the Exchange about Bagging/Receiving of orders/contracts",
     "Bagging/Receiving of orders/contracts", "PAM_27102026101631_PressRelease27102026.pdf", "press_release"),
    ("Larsen & Toubro Limited has informed the Exchange regarding 'Analyst Presentation.- Q2 / H1 FY27'.", "Updates",
     "PAM_27102026183653_AnalystPresentationSep2026.pdf", "results"),
    ("Avenue Supermarts Limited has informed the Exchange about Action(s) initiated or orders passed",
     "Action(s) initiated or orders passed", None, "litigation"),
    ("Bajaj Finance Limited has informed the Exchange regarding allotment of 2,12,000 securities pursuant to Non "
     "Convertible Securities at its meeting held on October 21, 2026", "Allotment of Securities", None, "fund_raise"),
    ("Persistent Systems Limited has informed the Exchange about issue of Securities", "Issue of Securities", None,
     "fund_raise"),
    ("Persistent Systems Limited has informed the Exchange regarding Outcome of Committee Meeting held on October 21, "
     "2026.", "Committee Meeting Updates",
     "PERSISTENTUSER1_21102026191632_PersistentSEOutcomeQIPissueopeningOct212026V3signed.pdf", "fund_raise"),
    ("Larsen & Toubro Limited has informed the Exchange regarding allotment of 21098 securities pursuant to ESOP/ESPS",
     "Allotment of Securities", None, "unclassified"),
    ("Dixon Technologies (India) Limited has informed the Exchange regarding 'Giving of guarantees or indemnity or "
     "becoming a surety for any third party'.", "Updates", None, "unclassified"),
    ("Polycab India Limited has informed the Exchange about Analyst(s)/Investor(s) meet.", "General Updates", None,
     "investor_meetings"),
    # Persistent Q2 FY27: the LLM labelled this results once and unclassified on a re-run; a rule makes it stable
    ("Outcome of the Board Meeting", "Outcome of Board Meeting", None, "results"),
])
def test_rules(subject, raw_category, attachment, expected):
    assert classify_rule(subject, raw_category, attachment) == expected


def test_unmatched_returns_none():
    assert classify_rule("Initial Public Offer of Jio Platforms Limited", "General Updates", None) is None


def test_tier_map_covers_all_categories():
    assert set(TIER_BY_CATEGORY) == set(CATEGORIES)


def test_tier_follows_category():
    assert tier_for("results", "Financial Results for the quarter ended September 30, 2026") == "critical"
    assert tier_for("dividend", "Record date for interim dividend") == "notable"
    assert tier_for("agm_egm", "Notice of AGM") == "routine"


@pytest.mark.parametrize("subject", [
    "Infosys Limited has informed the Exchange regarding 'Infosys to Announce Second Quarter Results on October 23, 2026'.",
    "The meeting of the Board of Directors of the Company is scheduled on October 30, 2026, inter alia, to consider "
    "and approve a. the standalone and consolidated unaudited financial results of the Company",
    "Intimation of Board Meeting to consider financial results",
])
def test_scheduling_notices_are_routine(subject):
    assert tier_for("results", subject) == "routine"

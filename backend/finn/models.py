"""Shared data shapes. Every other module speaks in these types."""
import hashlib
from datetime import date, datetime
from typing import Literal, get_args
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator

IST = ZoneInfo("Asia/Kolkata")

Category = Literal[
    "results", "M&A", "fund_raise", "management_change", "litigation", "insider_trading",
    "earnings_call", "investor_meetings", "credit_rating", "dividend", "bonus_split", "capex",
    "press_release", "postal_ballot", "agm_egm", "pledging", "unclassified",
]
CATEGORIES: tuple[str, ...] = get_args(Category)
Tier = Literal["critical", "notable", "routine"]


def _ist(value: datetime) -> datetime:
    return value.replace(tzinfo=IST) if value.tzinfo is None else value.astimezone(IST)


class Announcement(BaseModel):
    id: str
    symbol: str
    company: str
    filed_at: datetime
    subject: str
    body: str
    attachment_url: str | None
    raw_category: str | None
    source: Literal["nse", "bse"]

    _ist = field_validator("filed_at")(_ist)

    @staticmethod
    def make_id(symbol: str, filed_at: datetime, subject: str) -> str:
        return hashlib.sha1(f"{symbol}|{_ist(filed_at).isoformat()}|{subject}".encode()).hexdigest()


class MetricRow(BaseModel):
    current: float
    prev_q: float
    year_ago: float
    qoq_pct: float | None
    yoy_pct: float | None


class ResultsCard(BaseModel):
    status: Literal["ok", "unreadable"]
    layout: Literal["corporate", "lender"]
    basis: Literal["consolidated", "standalone"] | None
    period_end: date | None
    metrics: dict[str, MetricRow]  # ordered: insertion order is display order
    not_applicable: list[str] = []
    verified: bool | None = None
    mismatches: list[str] = []
    unit: Literal["₹ Cr"] = "₹ Cr"


class PersonProfile(BaseModel):
    name: str
    role: str
    change: Literal["appointed", "resigned", "retired"]
    effective_date: str | None
    background: str
    prior_roles: list[str]


class EnrichedAnnouncement(BaseModel):
    announcement: Announcement
    category: Category
    tier: Tier
    summary: str | None = None
    results: ResultsCard | None = None
    profile: PersonProfile | None = None


class DocRef(BaseModel):
    title: str
    url: str | None
    filed_at: datetime


class Event(BaseModel):
    id: str
    symbol: str
    company: str
    category: Category
    tier: Tier
    first_at: datetime
    last_at: datetime
    headline: str
    summary: str | None
    results: ResultsCard | None
    profile: PersonProfile | None
    documents: list[DocRef]
    price_change_pct: float | None
    volume_multiple: float | None


class Bar(BaseModel):
    date: date
    close: float
    volume: float


class Signal(BaseModel):
    id: str
    symbol: str
    date: date
    kind: Literal["volume_spike", "price_move"]
    value: float  # volume multiple, or % move
    threshold: float
    close: float


class Settings(BaseModel):
    price_move_pct: float = Field(5.0, ge=0.5, le=50)
    volume_multiple: float = Field(2.0, ge=1.1, le=10)
    volume_lookback_days: int = Field(20, ge=5, le=120)
    alert_categories: list[Category] = [
        "results", "M&A", "management_change", "fund_raise", "litigation", "pledging",
    ]


class Alert(BaseModel):
    id: str
    symbol: str
    title: str
    source: Literal["announcement", "signal"]
    ref_id: str
    at: datetime


class PushSnapshot(BaseModel):
    as_of: datetime
    announcements: list[EnrichedAnnouncement]
    failed_sources: list[str] = []


class EventsFile(BaseModel):
    """events.json: what the browser's Brief reads."""
    as_of: datetime
    events: list[Event]

"""The mock portfolio and research demo set, loaded from portfolio.yaml."""
from functools import cache
from pathlib import Path

import yaml
from pydantic import BaseModel

PORTFOLIO_FILE = Path(__file__).with_name("portfolio.yaml")


class Holding(BaseModel):
    symbol: str
    name: str
    sector: str
    bse_code: str | None = None


class Portfolio(BaseModel):
    holdings: list[Holding]
    research: list[str]

    def holding(self, symbol: str) -> Holding | None:
        return next((h for h in self.holdings if h.symbol == symbol), None)


@cache
def load_portfolio(path: Path = PORTFOLIO_FILE) -> Portfolio:
    return Portfolio.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

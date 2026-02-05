from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RateHistory:
    currency_code: str
    timestamp: datetime
    currency_name: str
    ttb: float
    tts: float
    deal_bas_r: float
    source_date: str  # Original date from API (YYYYMMDD)
    created_at: Optional[datetime] = None
    # Derived convenience fields (stored for spread analysis)
    buy_rate: Optional[float] = None   # alias: ttb
    sell_rate: Optional[float] = None  # alias: tts
    spread: Optional[float] = None     # sell_rate - buy_rate

    def get_rate_by_type(self, rate_type: str) -> float:
        rate_map = {
            "TTS": self.tts,
            "TTB": self.ttb,
            "DEAL_BAS_R": self.deal_bas_r,
        }
        return rate_map.get(rate_type.upper(), self.deal_bas_r)

    def calculate_change(self, previous: "RateHistory", rate_type: str = "DEAL_BAS_R") -> Optional[float]:
        if not previous:
            return None

        current_rate = self.get_rate_by_type(rate_type)
        previous_rate = previous.get_rate_by_type(rate_type)

        if previous_rate == 0:
            return None

        return ((current_rate - previous_rate) / previous_rate) * 100

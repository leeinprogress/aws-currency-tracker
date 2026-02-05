import os
import requests
import certifi
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class KoreaEximAPIError(Exception):
    """KoreaExim API specific errors"""
    def __init__(self, message: str, result_code: int = None):
        self.result_code = result_code
        super().__init__(message)


class RateLimitExceededError(KoreaEximAPIError):
    """Daily API call limit exceeded (1000 calls/day)"""
    pass


class NoDataAvailableError(KoreaEximAPIError):
    """No data available (non-business day or before 11am)"""
    pass


@dataclass
class ExchangeRate:
    cur_unit: str
    cur_nm: str
    ttb: float
    tts: float
    deal_bas_r: float


class KoreaEximExchangeRateClient:
    BASE_URL = "https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON"
    
    RESULT_CODES = {
        1: "Success",
        2: "DATA_CODE_ERROR",
        3: "AUTHKEY_ERROR", 
        4: "RATE_LIMIT_EXCEEDED",
    }
    
    def __init__(self, authkey: Optional[str] = None):
        self.authkey = authkey or os.environ.get('KOREAEXIM_AUTHKEY', '')
        if not self.authkey:
            raise ValueError("KoreaExim authkey is required")
    
    def fetch_rates(
        self, 
        searchdate: Optional[str] = None,
        data: str = "AP01"
    ) -> List[ExchangeRate]:
        if not searchdate:
            searchdate = datetime.now().strftime("%Y%m%d")
        
        params = {
            "authkey": self.authkey,
            "searchdate": searchdate,
            "data": data
        }
        
        try:
            response = self._make_request(params)
            response.raise_for_status()
            
            if not response.content or len(response.content.strip()) == 0:
                raise NoDataAvailableError(
                    f"No data available for {searchdate} (non-business day or before 11am)"
                )
            
            data_list = response.json()
            
            if not isinstance(data_list, list):
                raise KoreaEximAPIError(f"Unexpected API response format: {type(data_list)}")
            
            if not data_list:
                raise NoDataAvailableError(
                    f"No exchange rate data for {searchdate}"
                )
            
            return self._parse_rates(data_list)
            
        except requests.exceptions.RequestException as e:
            logger.error("api_request_failed", error=str(e))
            raise KoreaEximAPIError(f"Failed to fetch exchange rates: {str(e)}")
    
    def _make_request(self, params: dict) -> requests.Response:
        try:
            return requests.get(self.BASE_URL, params=params, timeout=10, verify=certifi.where())
        except requests.exceptions.SSLError:
            logger.warning("ssl_fallback_triggered")
            return requests.get(self.BASE_URL, params=params, timeout=10, verify=True)
    
    def _parse_rates(self, data_list: list) -> List[ExchangeRate]:
        rates = []
        for item in data_list:
            result_code = item.get("result")
            
            if result_code == 4:
                raise RateLimitExceededError(
                    "Daily API call limit exceeded (1000 calls/day)",
                    result_code=4
                )
            
            if result_code != 1:
                continue
            
            cur_unit = item.get("cur_unit", "").strip()
            if not cur_unit:
                continue
            
            try:
                rate = ExchangeRate(
                    cur_unit=cur_unit,
                    cur_nm=item.get("cur_nm", "").strip(),
                    ttb=self._parse_rate(item.get("ttb", "")),
                    tts=self._parse_rate(item.get("tts", "")),
                    deal_bas_r=self._parse_rate(item.get("deal_bas_r", ""))
                )
                rates.append(rate)
            except (ValueError, KeyError) as e:
                logger.warning("skipping_invalid_rate", currency=cur_unit, error=str(e))
                continue
        
        return rates
    
    def _parse_rate(self, rate_str: str) -> float:
        if not rate_str:
            return 0.0
        cleaned = str(rate_str).replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

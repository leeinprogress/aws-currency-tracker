"""
Korea Export-Import Bank (KoreaExim) Exchange Rate API Client
"""
import os
import requests
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class ExchangeRate:
    """Exchange rate data model"""
    cur_unit: str  # Currency code (e.g., USD)
    cur_nm: str    # Currency name (e.g., US Dollar)
    ttb: float     # Telegraphic Transfer Buying rate
    tts: float     # Telegraphic Transfer Selling rate
    deal_bas_r: float  # Deal base rate


class KoreaEximExchangeRateClient:
    """Korea Export-Import Bank Exchange Rate API Client"""
    
    BASE_URL = "https://www.koreaexim.go.kr/ir/HPHKIR020M01"
    
    def __init__(self, authkey: Optional[str] = None):
        """
        Args:
            authkey: KoreaExim API authentication key
        """
        self.authkey = authkey or os.environ.get('KOREAEXIM_AUTHKEY', '')
        if not self.authkey:
            raise ValueError("KoreaExim authkey is required")
    
    def fetch_rates(
        self, 
        searchdate: Optional[str] = None,
        data: str = "AP01"
    ) -> List[ExchangeRate]:
        """
        Fetch exchange rate data
        
        Args:
            searchdate: Request date in YYYYMMDD format (None for today)
            data: Request type (AP01: Exchange rates, AP02: Loan rates, AP03: International rates)
        
        Returns:
            List of ExchangeRate objects
        """
        if not searchdate:
            # Format today's date as YYYYMMDD
            searchdate = datetime.now().strftime("%Y%m%d")
        
        params = {
            "apino": 2,
            "viewtype": "C",
            "authkey": self.authkey,
            "searchdate": searchdate,
            "data": data
        }
        
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            
            # API response is in JSON array format
            data_list = response.json()
            
            if not isinstance(data_list, list):
                raise ValueError(f"Unexpected API response format: {type(data_list)}")
            
            rates = []
            for item in data_list:
                try:
                    # Parse only required fields
                    rate = ExchangeRate(
                        cur_unit=item.get("CUR_UNIT", "").strip(),
                        cur_nm=item.get("CUR_NM", "").strip(),
                        ttb=self._parse_rate(item.get("TTB", "")),
                        tts=self._parse_rate(item.get("TTS", "")),
                        deal_bas_r=self._parse_rate(item.get("DEAL_BAS_R", ""))
                    )
                    rates.append(rate)
                except (ValueError, KeyError) as e:
                    # Skip items that fail to parse
                    print(f"Skipping invalid rate data: {item}, error: {e}")
                    continue
            
            return rates
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch exchange rates: {str(e)}")
        except ValueError as e:
            raise Exception(f"Failed to parse exchange rates: {str(e)}")
    
    def _parse_rate(self, rate_str: str) -> float:
        """
        Convert exchange rate string to float
        Handle comma-separated number strings (e.g., "1,450.50" -> 1450.50)
        """
        if not rate_str:
            return 0.0
        
        # Remove commas and convert to float
        cleaned = str(rate_str).replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    
    def get_rate_by_currency(
        self, 
        currency_code: str,
        rate_type: str = "TTS",
        searchdate: Optional[str] = None
    ) -> Optional[float]:
        """
        Get exchange rate for a specific currency
        
        Args:
            currency_code: Currency code (e.g., USD, EUR)
            rate_type: Rate type (TTS, TTB, DEAL_BAS_R)
            searchdate: Request date
        
        Returns:
            Exchange rate value (None if not found)
        """
        rates = self.fetch_rates(searchdate=searchdate)
        
        # Search by currency code (case-insensitive)
        currency_code_upper = currency_code.upper()
        for rate in rates:
            if rate.cur_unit.upper() == currency_code_upper:
                if rate_type == "TTS":
                    return rate.tts
                elif rate_type == "TTB":
                    return rate.ttb
                elif rate_type == "DEAL_BAS_R":
                    return rate.deal_bas_r
                else:
                    raise ValueError(f"Invalid rate_type: {rate_type}. Must be TTS, TTB, or DEAL_BAS_R")
        
        return None
    
    def get_all_rates_dict(
        self,
        rate_type: str = "TTS",
        searchdate: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Get all exchange rates as a dictionary
        
        Args:
            rate_type: Rate type (TTS, TTB, DEAL_BAS_R)
            searchdate: Request date
        
        Returns:
            Dictionary mapping currency codes to rates
        """
        rates = self.fetch_rates(searchdate=searchdate)
        result = {}
        
        for rate in rates:
            currency_code = rate.cur_unit.upper()
            if rate_type == "TTS":
                result[currency_code] = rate.tts
            elif rate_type == "TTB":
                result[currency_code] = rate.ttb
            elif rate_type == "DEAL_BAS_R":
                result[currency_code] = rate.deal_bas_r
        
        return result


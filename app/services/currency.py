"""Currency conversion service"""

from typing import Dict, Any, Optional
from decimal import Decimal
import httpx
from datetime import datetime, timedelta

from app.core.cache import cache, cached
from app.core.config import settings

class CurrencyService:
    """Service for multi-currency support"""
    
    def __init__(self):
        self.base_currency = "INR"
        self.exchange_api_url = "https://api.exchangerate-api.com/v4/latest/"
        
    @cached(key_prefix="exchange_rates", expire=3600)
    async def get_exchange_rates(self) -> Dict[str, float]:
        """Get current exchange rates"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.exchange_api_url}{self.base_currency}")
            data = response.json()
            return data["rates"]
            
    async def convert_price(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str
    ) -> Decimal:
        """Convert price between currencies"""
        if from_currency == to_currency:
            return amount
            
        rates = await self.get_exchange_rates()
        
        # Convert to base currency first
        if from_currency != self.base_currency:
            amount = amount / Decimal(str(rates[from_currency]))
            
        # Then convert to target currency
        if to_currency != self.base_currency:
            amount = amount * Decimal(str(rates[to_currency]))
            
        return amount.quantize(Decimal("0.01"))
        
    def format_currency(
        self,
        amount: Decimal,
        currency: str,
        locale: str = "en"
    ) -> str:
        """Format currency for display"""
        currency_symbols = {
            "INR": "₹",
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "AED": "د.إ",
            "SGD": "S$"
        }
        
        symbol = currency_symbols.get(currency, currency)
        
        # Format based on locale
        if locale == "en_IN" and currency == "INR":
            # Indian numbering system
            return f"{symbol}{self._format_indian_currency(amount)}"
        else:
            # Standard formatting
            return f"{symbol}{amount:,.2f}"
            
    def _format_indian_currency(self, amount: Decimal) -> str:
        """Format currency in Indian numbering system"""
        s = str(int(amount))
        if len(s) <= 3:
            return f"{s}.{int(amount % 1 * 100):02d}"
            
        # Add commas
        result = s[-3:]
        s = s[:-3]
        while s:
            result = s[-2:] + "," + result
            s = s[:-2]
            
        return f"{result}.{int(amount % 1 * 100):02d}"
        
    async def get_regional_pricing(
        self,
        base_price: Decimal,
        target_country: str
    ) -> Dict[str, Any]:
        """Calculate regional pricing with purchasing power parity"""
        # Simplified PPP factors (in real app, use World Bank data)
        ppp_factors = {
            "IN": 1.0,
            "US": 3.5,
            "GB": 3.2,
            "AE": 2.8,
            "SG": 2.5,
            "BD": 0.8,
            "LK": 0.9
        }
        
        country_currencies = {
            "IN": "INR",
            "US": "USD",
            "GB": "GBP",
            "AE": "AED",
            "SG": "SGD",
            "BD": "BDT",
            "LK": "LKR"
        }
        
        factor = ppp_factors.get(target_country, 1.0)
        currency = country_currencies.get(target_country, "INR")
        
        # Adjust price based on PPP
        adjusted_price = base_price * Decimal(str(factor))
        
        # Convert to local currency
        local_price = await self.convert_price(
            adjusted_price,
            "INR",
            currency
        )
        
        return {
            "original_price": base_price,
            "local_price": local_price,
            "currency": currency,
            "ppp_adjusted": True,
            "factor": factor
        }

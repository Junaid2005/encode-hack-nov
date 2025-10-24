import yfinance as yf
from typing import Dict, Any, Optional
import logging
import pandas as pd
import numpy as np

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CryptoDataFetcher:
    """Class to handle cryptocurrency data fetching using yfinance"""
    
    def __init__(self):
        self.supported_cryptos = {
            'BTC': 'BTC-USD',
            'ETH': 'ETH-USD', 
            'SOL': 'SOL-USD',
            'SPY': '^GSPC',
            'USD/GBP': 'USDGBP=X'
        }
    
    def get_crypto_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current price and change percentage for a single cryptocurrency
        
        Args:
            symbol (str): Crypto symbol (e.g., 'BTC', 'ETH', 'SOL')
            
        Returns:
            Dict containing price, change, and metadata or None if error
        """
        try:
            if symbol.upper() not in self.supported_cryptos:
                logger.error(f"Unsupported crypto symbol: {symbol}")
                return None
                
            ticker_symbol = self.supported_cryptos[symbol.upper()]
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info
            
            price = f"${info.get('regularMarketPrice', 0):,.2f}"
            change_percent = f"{info.get('regularMarketChangePercent', 0):,.2f}%"
            change_amount = f"${info.get('regularMarketChange', 0):,.2f}"
            
            return {
                'symbol': symbol.upper(),
                'price': price,
                'change_percent': change_percent,
                'change_amount': change_amount,
                'currency': 'USD',
                'market_cap': info.get('marketCap', 0),
                'volume': info.get('volume', 0),
                'last_updated': info.get('regularMarketTime', 'N/A'),
                'chart_data': [np.random.uniform(1, 100000) for _ in range(40)],
            }
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {str(e)}")
            return None
    
    def get_multiple_crypto_prices(self, symbols: list) -> Dict[str, Dict[str, Any]]:
        """
        Get prices for multiple cryptocurrencies
        
        Args:
            symbols (list): List of crypto symbols
            
        Returns:
            Dict mapping symbol to price data
        """
        results = {}
        
        for symbol in symbols:
            data = self.get_crypto_price(symbol)
            if data:
                results[symbol.upper()] = data
            else:
                # Fallback to dummy data if API fails
                results[symbol.upper()] = None                
        return results
    
    def get_top_crypto_prices(self, limit: int = 5) -> Dict[str, Dict[str, Any]]:
        """
        Get prices for top cryptocurrencies
        
        Args:
            limit (int): Number of top cryptos to fetch
            
        Returns:
            Dict mapping symbol to price data
        """
        top_symbols = list(self.supported_cryptos.keys())[:limit]
        return self.get_multiple_crypto_prices(top_symbols)

# Convenience function for easy import
def get_crypto_data(symbols: list = ['BTC', 'ETH', 'SOL']) -> Dict[str, Dict[str, Any]]:
    """
    Convenience function to get crypto data
    
    Args:
        symbols (list): List of crypto symbols to fetch
        
    Returns:
        Dict mapping symbol to price data
    """
    print(f"Fetching crypto data for {symbols}")
    fetcher = CryptoDataFetcher()
    return fetcher.get_multiple_crypto_prices(symbols)
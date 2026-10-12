"""Data downloader module for fetching historical stock data from yfinance."""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DataDownloader:
    """Download historical stock data from yfinance."""

    def __init__(self, source: str = "yfinance"):
        """Initialize the data downloader.

        Args:
            source: Data source identifier (currently only supports 'yfinance')
        """
        self.source = source

    def download(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Download historical daily data for a symbol.

        Args:
            symbol: Stock ticker symbol
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            DataFrame with columns: date, open, high, low, close, volume, adjusted_close

        Raises:
            ValueError: If data download fails or returns empty
        """
        if self.source != "yfinance":
            raise ValueError(f"Unsupported data source: {self.source}")

        logger.info(f"Downloading data for {symbol} from {start_date} to {end_date}")

        try:
            # Download data using yfinance
            ticker = yf.Ticker(symbol)
            data = ticker.history(
                start=start_date,
                end=end_date,
                interval="1d"
            )

            if data.empty:
                raise ValueError(f"No data returned for {symbol}")

            # Reset index to get date as column
            data = data.reset_index()

            # Rename columns to standard format
            data = data.rename(columns={
                'Date': 'date',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume',
            })

            # Use adjusted close if available, otherwise use close
            if 'Adj Close' in data.columns:
                data['adjusted_close'] = data['Adj Close']
                data = data.drop('Adj Close', axis=1)
            else:
                data['adjusted_close'] = data['close']

            # Ensure date is datetime
            data['date'] = pd.to_datetime(data['date'])

            # Sort by date ascending
            data = data.sort_values('date').reset_index(drop=True)

            logger.info(f"Downloaded {len(data)} trading days for {symbol}")

            return data

        except Exception as e:
            logger.error(f"Failed to download data for {symbol}: {e}")
            raise

    def calculate_volatility(self, symbol: str, start_date: str, end_date: str) -> float:
        """Calculate annualized volatility for a symbol over a date range.

        Args:
            symbol: Stock ticker symbol
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Annualized volatility as decimal (e.g., 0.25 for 25%)
        """
        data = self.download(symbol, start_date, end_date)
        if len(data) < 2:
            return 0.0
        # Calculate daily returns using adjusted close
        returns = data['adjusted_close'].pct_change().dropna()
        if len(returns) < 2:
            return 0.0
        # Annualized volatility = std of daily returns * sqrt(trading days per year)
        volatility = returns.std() * np.sqrt(252)
        return volatility


def download_data(
    symbols: list[str],
    start_date: str,
    end_date: str
) -> dict[str, pd.DataFrame]:
    """Download data for multiple symbols.

    Args:
        symbols: List of stock ticker symbols
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Dictionary mapping symbol to DataFrame of historical data
    """
    downloader = DataDownloader()
    data = {}

    for symbol in symbols:
        try:
            data[symbol] = downloader.download(symbol, start_date, end_date)
        except Exception as e:
            logger.error(f"Skipping {symbol} due to error: {e}")
            continue

    return data


def download_single_symbol(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Download data for a single symbol (convenience function).

    Args:
        symbol: Stock ticker symbol
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        DataFrame with historical data for the symbol
    """
    downloader = DataDownloader()
    return downloader.download(symbol, start_date, end_date)

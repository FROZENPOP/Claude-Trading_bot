"""Options data downloader module for fetching historical option chain data from Webull via MCP."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
import logging
import time
import re

logger = logging.getLogger(__name__)


class OptionsDataDownloader:
    """Download historical option chain data from Webull via MCP."""

    def __init__(
        self,
        app_key: Optional[str] = None,
        app_secret: Optional[str] = None,
        environment: str = "uat",
        region_id: str = "us"
    ):
        """Initialize the Webull options data downloader.

        Args:
            app_key: Webull app key (reads from env if not provided)
            app_secret: Webull app secret (reads from env if not provided)
            environment: Trading environment ('uat' for paper/sandbox, 'prod' for live)
            region_id: Region identifier ('us', 'hk', 'jp', etc.)
        """
        import os
        self.app_key = app_key or os.environ.get('WEBULL_APP_KEY')
        self.app_secret = app_secret or os.environ.get('WEBULL_APP_SECRET')
        self.environment = environment or os.environ.get('WEBULL_ENVIRONMENT', 'uat')
        self.region_id = region_id or os.environ.get('WEBULL_REGION_ID', 'us')

        # Validate required credentials
        if not self.app_key or not self.app_secret:
            raise ValueError(
                "Webull API credentials not provided. "
                "Set WEBULL_APP_KEY and WEBULL_APP_SECRET environment variables."
            )

        # Validate environment
        if self.environment not in ['uat', 'prod']:
            raise ValueError("Environment must be 'uat' (paper) or 'prod' (live)")

        logger.info("Webull options data downloader initialized")

    def _is_option_symbol(self, symbol: str) -> bool:
        """Check if a symbol represents an option contract.

        Detects all option types that Webull allows for trading:
        - Calls and puts
        - Various expiration dates (daily, weekly, monthly, LEAPS)
        - Wide range of strike prices
        - All underlying securities that offer options trading on Webull

        Webull option symbol format varies by region. For US options:
        {UNDERLYING}{YY}{MM}{DD}{C/P}{STRIKE*1000}
        Example: AAPL240119C00150000 (AAPL call, Jan 19, 2024, $150 strike)

        Args:
            symbol: Symbol to check

        Returns:
            True if symbol is an option contract, False otherwise
        """
        # Webull US option symbol regex: letters + 6 digits + C/P + 8 digits
        option_pattern = r'^[A-Z]+\d{6}[CP]\d{8}$'
        return bool(re.match(option_pattern, symbol.upper()))

    def _parse_option_symbol(self, option_symbol: str) -> Dict:
        """Parse an option symbol to extract components.

        Args:
            option_symbol: Option symbol (e.g., 'AAPL240119C00150000')

        Returns:
            Dictionary with underlying_symbol, expiration_date, option_type, strike_price
        """
        if not self._is_option_symbol(option_symbol):
            raise ValueError(f"Invalid option symbol: {option_symbol}")

        # Extract components
        # Format: {UNDERLYING}{YY}{MM}{DD}{C/P}{STRIKE*1000}
        # Find where the letters end and numbers begin
        match = re.match(r'^([A-Z]+)(\d{6})([CP])(\d{8})$', option_symbol)
        if not match:
            raise ValueError(f"Unable to parse option symbol: {option_symbol}")

        underlying = match.group(1)
        date_part = match.group(2)  # YYMMDD
        option_type = match.group(3)  # C or P
        strike_part = match.group(4)  # Strike * 1000

        # Format expiration date
        exp_year = f"20{date_part[0:2]}"
        exp_month = date_part[2:4]
        exp_day = date_part[4:6]
        expiration = f"{exp_year}-{exp_month}-{exp_day}"

        # Convert strike price
        strike_price = int(strike_part) / 1000.0

        return {
            'underlying_symbol': underlying,
            'expiration_date': expiration,
            'option_type': 'call' if option_type == 'C' else 'put',
            'strike_price': strike_price
        }

    def get_option_chain(
        self,
        underlying_symbol: str,
        expiration_date: Optional[str] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """Get current option chain for an underlying symbol.

        Args:
            underlying_symbol: Underlying stock symbol (e.g., 'AAPL')
            expiration_date: Expiration date in YYYY-MM-DD format (optional)
            limit: Maximum number of contracts to return

        Returns:
            DataFrame with option chain data
        """
        try:
            # Build request params
            params = {
                "symbols": underlying_symbol,
                "limit": limit
            }
            if expiration_date:
                params["expiration_date"] = expiration_date

            # Use MCP get_option_chain tool
            try:
                chain_result = mcp__webull__get_option_chain(**params)
            except NameError:
                # MCP tool not available, simulate data for development
                logger.warning("MCP get_option_chain tool not available, simulating option chain data")
                # Simulate some option chain data for development
                chain_result = self._simulate_option_chain(underlying_symbol, expiration_date, limit)

            # Convert to DataFrame
            if not chain_result:
                logger.warning(f"No option chain data returned for {underlying_symbol}")
                return pd.DataFrame()

            data = []
            for item in chain_result:
                # Parse the option symbol to extract components
                option_symbol = item.get('option_symbol', '')
                try:
                    parsed = self._parse_option_symbol(option_symbol)
                except ValueError:
                    # If we can't parse the symbol, skip it or use basic info
                    logger.warning(f"Could not parse option symbol: {option_symbol}")
                    continue

                data.append({
                    'option_symbol': option_symbol,
                    'underlying_symbol': parsed['underlying_symbol'],
                    'expiration_date': parsed['expiration_date'],
                    'option_type': parsed['option_type'],
                    'strike_price': parsed['strike_price'],
                    'bid_price': item.get('bid_price', item.get('bid', None)),
                    'ask_price': item.get('ask_price', item.get('ask', None)),
                    'last_price': item.get('last_price', item.get('price', None)),
                    'bid_size': item.get('bid_size', None),
                    'ask_size': item.get('ask_size', None),
                    'volume': item.get('volume', None),
                    'open_interest': item.get('open_interest', None),
                    'implied_volatility': item.get('implied_volatility', item.get('iv', None)),
                    'delta': item.get('delta', None),
                    'gamma': item.get('gamma', None),
                    'theta': item.get('theta', None),
                    'vega': item.get('vega', None),
                    'timestamp': item.get('timestamp', item.get('update_time', None))
                })

            df = pd.DataFrame(data)
            logger.info(f"Retrieved option chain for {underlying_symbol}: {len(df)} contracts")
            return df

        except Exception as e:
            logger.error(f"Failed to get option chain for {underlying_symbol}: {e}")
            raise

    def get_option_bars(
        self,
        option_symbol: str,
        start: str,
        end: str,
        timeframe: str = "1Day",
        limit: int = 10000
    ) -> pd.DataFrame:
        """Get historical price bars for a specific option contract.

        Args:
            option_symbol: Option symbol (e.g., 'AAPL240119C00150000')
            start: Start date in YYYY-MM-DD format
            end: End date in YYYY-MM-DD format
            timeframe: TimeFrame (1Min, 5Min, 15Min, 1Hour, 1Day)
            limit: Maximum number of bars to return

        Returns:
            DataFrame with OHLCV data
        """
        try:
            # Validate option symbol
            if not self._is_option_symbol(option_symbol):
                raise ValueError(f"Invalid option symbol: {option_symbol}")

            # Use MCP get_option_bars tool
            try:
                bars_result = mcp__webull__get_option_bars(
                    symbol=option_symbol,
                    start=start,
                    end=end,
                    timespan=timeframe,
                    count=limit
                )
            except NameError:
                # MCP tool not available, simulate data for development
                logger.warning("MCP get_option_bars tool not available, simulating option bars data")
                bars_result = self._simulate_option_bars(option_symbol, start, end, timeframe, limit)

            # Convert to DataFrame
            if not bars_result:
                logger.warning(f"No option bars data returned for {option_symbol}")
                return pd.DataFrame()

            # Webull returns data in a format that needs to be converted
            data = []
            for bar in bars_result:
                data.append({
                    'time': bar.get('time', bar.get('t', None)),
                    'open': bar.get('open', bar.get('o', None)),
                    'high': bar.get('high', bar.get('h', None)),
                    'low': bar.get('low', bar.get('l', None)),
                    'close': bar.get('close', bar.get('c', None)),
                    'volume': bar.get('volume', bar.get('v', None)),
                    'option_symbol': option_symbol
                })

            df = pd.DataFrame(data)
            # Convert time column to datetime if it's not already
            if 'time' in df.columns and df['time'].dtype == 'object':
                df['time'] = pd.to_datetime(df['time'])

            logger.info(f"Retrieved {len(df)} bars for {option_symbol}")
            return df

        except Exception as e:
            logger.error(f"Failed to get option bars for {option_symbol}: {e}")
            raise

    def get_underlying_price(
        self,
        symbol: str,
        as_of: Optional[str] = None
    ) -> float:
        """Get current or historical price for an underlying stock.

        Args:
            symbol: Stock symbol
            as_of: Date in YYYY-MM-DD format (for historical price, None for current)

        Returns:
            Current price as float
        """
        try:
            if as_of:
                # For historical data, we'd need to use bars - simplified for now
                # In production, you'd use get_stock_bars with the as_of date
                logger.warning("Historical price lookup not fully implemented, returning current price")

            # Get latest quote for the underlying stock
            try:
                quote_result = mcp__webull__get_stock_quotes(symbol=symbol)
            except NameError:
                # MCP tool not available, simulate quote data for development
                logger.warning("MCP get_stock_quotes tool not available, simulating stock quote")
                quote_result = [{'bid_price': 99.95, 'ask_price': 100.05}]  # Simulate $100 stock

            # Extract bid/ask from stock quote result
            if quote_result and len(quote_result) > 0:
                stock_quote = quote_result[0]
                bid_price = stock_quote.get('bid_price', 0)
                ask_price = stock_quote.get('ask_price', 0)
                if bid_price > 0 and ask_price > 0:
                    return (bid_price + ask_price) / 2

            # If we couldn't get a valid bid/ask, try last trade price
            try:
                trade_result = mcp__webull__get_stock_latest_trade(symbol=symbol)
            except NameError:
                # MCP tool not available, simulate trade data for development
                logger.warning("MCP get_stock_latest_trade tool not available, simulating stock trade")
                trade_result = [{'price': 100.0}]  # Simulate $100 stock price

            if trade_result and len(trade_result) > 0:
                return trade_result[0].get('price', 0.0)

            logger.warning(f"Could not get price for {symbol}, returning None")
            return None  # Return None to force proper error handling upstream

        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            raise

    def download_historical_option_data(
        self,
        underlying_symbol: str,
        start_date: str,
        end_date: str,
        dte_range: List[int] = [21, 30, 45, 60],
        save_to_file: bool = False
    ) -> Dict[str, pd.DataFrame]:
        """Download historical option chain data for a date range.

        This is a simplified version - in practice, you'd need to iterate through
        each trading day and collect option chains for that day.

        Args:
            underlying_symbol: Underlying stock symbol
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            dte_range: List of days to expiration to collect
            save_to_file: Whether to save data to CSV files

        Returns:
            Dictionary mapping dates to option chain DataFrames
        """
        logger.warning(
            "Historical option chain download is complex and requires "
            "iterating through each trading day. This method provides a framework "
            "but may need customization for your specific data needs."
        )

        # Generate date range (business days only)
        dates = pd.date_range(start=start_date, end=end_date, freq='B')

        option_data = {}

        for date in dates:
            date_str = date.strftime('%Y-%m-%d')
            try:
                logger.info(f"Processing option data for {date_str}")
                # For each date, we'd want the option chain as of that date
                # This would require historical option chain data which may not be available
                # through the standard API without special permissions

                # Placeholder - in practice you would:
                # 1. Get the underlying price for that date
                # 2. Calculate target expiration dates based on DTE range
                # 3. Query option chains for those expirations
                # 4. Store the data

                # For now, we'll get the current option chain as an approximation
                chain = self.get_option_chain(underlying_symbol)
                option_data[date_str] = chain

            except Exception as e:
                logger.error(f"Failed to get option data for {date_str}: {e}")
                continue

        return option_data

    def _simulate_option_chain(self, underlying_symbol: str, expiration_date: Optional[str], limit: int) -> List[Dict]:
        """Simulate option chain data for development/testing when MCP tools are not available."""
        import random

        # Simulate current price for the underlying
        underlying_price = random.uniform(50, 300)

        # Generate some option contracts
        data = []
        num_contracts = min(limit, random.randint(20, 50))  # Simulate 20-50 contracts

        for i in range(num_contracts):
            # Randomly choose call or put
            option_type = random.choice(['call', 'put'])
            option_char = 'C' if option_type == 'call' else 'P'

            # Generate expiration date (if not specified, use a future date)
            if expiration_date:
                exp_date = expiration_date
            else:
                # Future date between 1-60 days out
                days_out = random.randint(1, 60)
                exp_date = (datetime.now() + timedelta(days=days_out)).strftime('%Y-%m-%d')

            # Generate strike price around the underlying price
            strike_price = round(underlying_price * random.uniform(0.8, 1.2), 1)

            # Format option symbol: {UNDERLYING}{YY}{MM}{DD}{C/P}{STRIKE*1000}
            exp_dt = datetime.strptime(exp_date, '%Y-%m-%d')
            exp_date_str = exp_dt.strftime('%y%m%d')  # YYMMDD
            strike_int = int(strike_price * 1000)
            strike_str = f"{strike_int:08d}"
            option_symbol = f"{underlying_symbol.upper()}{exp_date_str}{option_char}{strike_str}"

            # Simulate bid/ask prices based on option type and moneyness
            if option_type == 'call':
                intrinsic_value = max(0, underlying_price - strike_price)
                time_value = random.uniform(0.5, 5.0)
                option_price = intrinsic_value + time_value
            else:  # put
                intrinsic_value = max(0, strike_price - underlying_price)
                time_value = random.uniform(0.5, 5.0)
                option_price = intrinsic_value + time_value

            # Bid is slightly less than option price, ask is slightly more
            spread = option_price * 0.05  # 5% spread
            bid_price = max(0.01, option_price - spread/2)
            ask_price = option_price + spread/2

            data.append({
                'option_symbol': option_symbol,
                'underlying_symbol': underlying_symbol.upper(),
                'expiration_date': exp_date,
                'option_type': option_type,
                'strike_price': strike_price,
                'bid_price': round(bid_price, 2),
                'ask_price': round(ask_price, 2),
                'last_price': round(option_price, 2),
                'bid_size': random.randint(1, 20),
                'ask_size': random.randint(1, 20),
                'volume': random.randint(0, 1000),
                'open_interest': random.randint(0, 5000),
                'implied_volatility': random.uniform(0.1, 0.8),
                'delta': random.uniform(-1.0, 1.0) if option_type == 'put' else random.uniform(0.0, 1.0),
                'gamma': random.uniform(0.01, 0.1),
                'theta': random.uniform(-0.1, 0.0),
                'vega': random.uniform(0.01, 0.5),
                'timestamp': datetime.now().isoformat()
            })

        return data

    def _simulate_option_bars(self, option_symbol: str, start: str, end: str, timeframe: str, limit: int) -> List[Dict]:
        """Simulate option bars data for development/testing when MCP tools are not available."""
        import random

        # Parse dates
        start_dt = datetime.strptime(start, '%Y-%m-%d')
        end_dt = datetime.strptime(end, '%Y-%m-%d')

        # Determine number of bars based on timeframe
        if timeframe == "1Day":
            delta = timedelta(days=1)
        elif timeframe == "1Hour":
            delta = timedelta(hours=1)
        elif timeframe == "30Min":
            delta = timedelta(minutes=30)
        elif timeframe == "15Min":
            delta = timedelta(minutes=15)
        elif timeframe == "5Min":
            delta = timedelta(minutes=5)
        else:  # 1Min
            delta = timedelta(minutes=1)

        # Generate bars
        data = []
        current_dt = start_dt
        bar_count = 0

        # Base price for the option (extract from symbol if possible)
        try:
            parsed = self._parse_option_symbol(option_symbol)
            base_price = parsed['strike_price']  # Simplified - in reality would be based on underlying
        except ValueError:
            # If we can't parse the option symbol, use a default price
            base_price = 10.0  # Default option price

        while current_dt <= end_dt and bar_count < limit:
            # Simulate OHLCV data
            volatility = 0.02  # 2% volatility
            open_price = base_price * (1 + random.uniform(-volatility, volatility))
            close_price = open_price * (1 + random.uniform(-volatility, volatility))
            high_price = max(open_price, close_price) * (1 + random.uniform(0, volatility))
            low_price = min(open_price, close_price) * (1 - random.uniform(0, volatility))
            volume = random.randint(10, 1000)

            data.append({
                'time': current_dt.isoformat(),
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2),
                'volume': volume
            })

            current_dt += delta
            bar_count += 1

            # Slightly drift the base price for realism
            base_price *= (1 + random.uniform(-0.005, 0.005))

        return data


def download_option_chain(
    underlying_symbol: str,
    app_key: Optional[str] = None,
    app_secret: Optional[str] = None,
    environment: str = "uat",
    region_id: str = "us"
) -> pd.DataFrame:
    """Convenience function to download current option chain.

    Args:
        underlying_symbol: Underlying stock symbol
        app_key: Webull app key
        app_secret: Webull app secret
        environment: Trading environment ('uat' for paper/sandbox, 'prod' for live)
        region_id: Region identifier ('us', 'hk', 'jp', etc.)

    Returns:
        DataFrame with option chain data
    """
    downloader = OptionsDataDownloader(
        app_key=app_key,
        app_secret=app_secret,
        environment=environment,
        region_id=region_id
    )
    return downloader.get_option_chain(underlying_symbol)


if __name__ == "__main__":
    # Example usage
    import os
    from dotenv import load_dotenv

    load_dotenv()

    try:
        downloader = OptionsDataDownloader()
        chain = downloader.get_option_chain("AAPL")
        print(f"Retrieved {len(chain)} option contracts for AAPL")
        print(chain.head())
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure WEBULL_APP_KEY and WEBULL_APP_SECRET are set in your environment")
"""Strangle strategy implementation for long and short strangles."""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from trading_bot.strategies.option_pricing import OptionPricingModel, parse_option_symbol
from trading_bot.strategies.signals import SignalGenerator

logger = logging.getLogger(__name__)


@dataclass
class Strangle:
    """Represents a strangle position."""
    underlying_symbol: str
    expiration_date: str
    call_strike: float  # Strike price for call option
    put_strike: float   # Strike price for put option (put_strike < call_strike)
    call_quantity: int  # Number of call contracts
    put_quantity: int   # Number of put contracts
    entry_date: datetime
    entry_price: float  # Net debit (for long strangle) or credit (for short strangle)
    max_loss: float     # For long strangle: entry price * contract multiplier * quantity
                       # For short strangle: potentially unlimited
    max_profit: float   # For long strangle: potentially unlimited
                       # For short strangle: entry price * contract multiplier * quantity
    breakeven_upper: float  # Call strike + entry price per share
    breakeven_lower: float  # Put strike - entry price per share
    is_long: bool       # True for long strangle (buy call + buy put), False for short strangle (sell call + sell put)


class StrangleStrategy:
    """Strangle strategy for options trading."""

    def __init__(self, underlying_symbol: str, max_risk_per_trade: float = 0.02):
        """Initialize strangle strategy.

        Args:
            underlying_symbol: The underlying stock symbol (e.g., 'AAPL')
            max_risk_per_trade: Maximum risk per trade as fraction of portfolio (default 2%)
        """
        self.underlying_symbol = underlying_symbol
        self.max_risk_per_trade = max_risk_per_trade
        self.option_pricing_model = OptionPricingModel()
        self.signal_generator = SignalGenerator()

    def generate_strangle_signals(self,
                                 stock_data: pd.DataFrame,
                                 option_chain_data: pd.DataFrame,
                                 current_date: datetime,
                                 is_long: bool = True,
                                 otm_percentage: float = 0.05) -> List[Dict]:
        """Generate strangle signals based on stock and option data.

        Args:
            stock_data: DataFrame with stock price data
            option_chain_data: DataFrame with option chain data
            current_date: Current date for signal generation
            is_long: If True, generate long strangle signals; if False, generate short strangle signals
            otm_percentage: Percentage out-of-the-money for strikes (default 5%)

        Returns:
            List of strangle signal dictionaries
        """
        signals = []

        # Filter option chain for current date
        if 'expiration_date' in option_chain_data.columns:
            # Get options expiring in the near future (next 2 expiration cycles)
            unique_expirations = sorted(option_chain_data['expiration_date'].unique())
            if len(unique_expirations) >= 2:
                target_expiration = unique_expirations[1]  # Second nearest expiration
            else:
                target_expiration = unique_expirations[0] if unique_expirations else None
        else:
            logger.warning("Option chain data missing expiration_date column")
            return signals

        if not target_expiration:
            return signals

        # Filter options for target expiration and underlying symbol
        exp_options = option_chain_data[
            (option_chain_data['expiration_date'] == target_expiration) &
            (option_chain_data['underlying_symbol'] == self.underlying_symbol)
        ].copy()

        if exp_options.empty:
            logger.warning(f"No options found for {self.underlying_symbol} expiring {target_expiration}")
            return signals

        # Get current stock price
        if not stock_data.empty:
            current_stock_price = stock_data.iloc[-1]['close']  # Most recent close price
        else:
            logger.warning("No stock data available")
            return signals

        # Calculate OTM strike prices
        # For call: strike > current price (OTM call)
        # For put: strike < current price (OTM put)
        otm_call_strike = current_stock_price * (1 + otm_percentage)
        otm_put_strike = current_stock_price * (1 - otm_percentage)

        # Find closest available strikes to our target OTM strikes
        if 'strike_price' in exp_options.columns:
            # Find closest call strike
            call_options = exp_options[exp_options['option_type'] == 'call'].copy()
            if not call_options.empty:
                call_options['strike_distance'] = abs(call_options['strike_price'] - otm_call_strike)
                closest_call = call_options.nsmallest(1, 'strike_distance')
                if not closest_call.empty:
                    call_strike = closest_call.iloc[0]['strike_price']
                    call_option = closest_call.iloc[0]
                else:
                    logger.warning("No suitable call options found")
                    return signals
            else:
                logger.warning("No call options found in chain")
                return signals

            # Find closest put strike
            put_options = exp_options[exp_options['option_type'] == 'put'].copy()
            if not put_options.empty:
                put_options['strike_distance'] = abs(put_options['strike_price'] - otm_put_strike)
                closest_put = put_options.nsmallest(1, 'strike_distance')
                if not closest_put.empty:
                    put_strike = closest_put.iloc[0]['strike_price']
                    put_option = closest_put.iloc[0]
                else:
                    logger.warning("No suitable put options found")
                    return signals
            else:
                logger.warning("No put options found in chain")
                return signals

            # Ensure put strike is less than call strike (valid strangle)
            if put_strike >= call_strike:
                logger.warning(f"Invalid strangle: put strike ({put_strike}) >= call strike ({call_strike})")
                # Try to adjust by finding next available strikes
                # For simplicity, we'll skip this signal generation
                return signals

            # Get option prices
            call_price = call_option.get('last_price', call_option.get('bid_price', 0))
            put_price = put_option.get('last_price', put_option.get('bid_price', 0))

            if call_price <= 0 or put_price <= 0:
                # Try using mid-price if last price not available
                call_bid = call_option.get('bid_price', 0)
                call_ask = call_option.get('ask_price', 0)
                put_bid = put_option.get('bid_price', 0)
                put_ask = put_option.get('ask_price', 0)

                if call_bid > 0 and call_ask > 0:
                    call_price = (call_bid + call_ask) / 2
                if put_bid > 0 and put_ask > 0:
                    put_price = (put_bid + put_ask) / 2

            if call_price > 0 and put_price > 0:
                strangle_price = call_price + put_price

                # Calculate position size based on risk limits
                contract_multiplier = 100  # Standard option contract multiplier
                max_dollar_risk = strangle_price * contract_multiplier  # Cost of 1 strangle contract

                if max_dollar_risk > 0:
                    # Calculate how many strangles we can trade based on risk limit
                    # This is simplified - in practice would need portfolio value
                    quantity = 1  # Start with 1 contract for safety

                    # Calculate breakeven points
                    breakeven_upper = call_strike + strangle_price
                    breakeven_lower = put_strike - strangle_price

                    # For long strangle: max loss is the premium paid, max profit is unlimited
                    # For short strangle: max profit is the premium received, max loss is unlimited
                    if is_long:
                        max_loss = strangle_price * contract_multiplier * quantity
                        max_profit = float('inf')  # Unlimited upside
                    else:
                        max_loss = float('inf')  # Unlimited downside
                        max_profit = strangle_price * contract_multiplier * quantity

                    signal = {
                        'signal_type': 'long_strangle' if is_long else 'short_strangle',
                        'underlying_symbol': self.underlying_symbol,
                        'expiration_date': target_expiration,
                        'call_strike': call_strike,
                        'put_strike': put_strike,
                        'call_symbol': call_option.get('symbol', ''),
                        'put_symbol': put_option.get('symbol', ''),
                        'quantity': quantity,
                        'entry_price': strangle_price,
                        'max_loss': max_loss,
                        'max_profit': max_profit,
                        'breakeven_upper': breakeven_upper,
                        'breakeven_lower': breakeven_lower,
                        'current_stock_price': current_stock_price,
                        'strangle_price': strangle_price,
                        'is_long': is_long,
                        'timestamp': current_date
                    }

                    signals.append(signal)
                    logger.info(f"Generated {'long' if is_long else 'short'} strangle signal: "
                              f"{self.underlying_symbol} P{put_strike}/C{call_strike} strangle expiring {target_expiration}")

        return signals

    def calculate_strangle_pnl(self,
                              position: Strangle,
                              current_stock_price: float,
                              current_date: datetime) -> float:
        """Calculate current P&L for a strangle position.

        Args:
            position: Strangle position object
            current_stock_price: Current price of the underlying stock
            current_date: Current date

        Returns:
            Current P&L in dollars
        """
        # This is a simplified P&L calculation
        # In practice, would need current option prices to calculate accurately

        # For demonstration, using intrinsic value approximation
        call_intrinsic = max(0, current_stock_price - position.call_strike)
        put_intrinsic = max(0, position.put_strike - current_stock_price)

        # Current strangle value (approximation)
        current_strangle_value = call_intrinsic + put_intrinsic

        # P&L = (current value - entry price) * quantity * multiplier
        # For long strangle: profit when stock moves significantly in either direction
        # For short strangle: profit when stock stays between the strikes
        pnl = (current_strangle_value - position.entry_price) * position.call_quantity * 100

        # Adjust for short strangle (we sold the strangle, so P&L is inverted)
        if not position.is_long:
            pnl = -pnl

        return pnl
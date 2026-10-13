"""Straddle strategy implementation for long and short straddles."""

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
class Straddle:
    """Represents a straddle position."""
    underlying_symbol: str
    expiration_date: str
    strike_price: float
    call_quantity: int  # Number of call contracts
    put_quantity: int   # Number of put contracts
    entry_date: datetime
    entry_price: float  # Net debit (for long straddle) or credit (for short straddle)
    max_loss: float     # For long straddle: entry price * contract multiplier * quantity
                       # For short straddle: potentially unlimited
    max_profit: float   # For long straddle: potentially unlimited
                       # For short straddle: entry price * contract multiplier * quantity
    breakeven_upper: float  # Strike price + entry price per share
    breakeven_lower: float  # Strike price - entry price per share
    is_long: bool       # True for long straddle (buy call + buy put), False for short straddle (sell call + sell put)


class StraddleStrategy:
    """Straddle strategy for options trading."""

    def __init__(self, underlying_symbol: str, max_risk_per_trade: float = 0.02):
        """Initialize straddle strategy.

        Args:
            underlying_symbol: The underlying stock symbol (e.g., 'AAPL')
            max_risk_per_trade: Maximum risk per trade as fraction of portfolio (default 2%)
        """
        self.underlying_symbol = underlying_symbol
        self.max_risk_per_trade = max_risk_per_trade
        self.option_pricing_model = OptionPricingModel()
        self.signal_generator = SignalGenerator()

    def generate_straddle_signals(self,
                                 stock_data: pd.DataFrame,
                                 option_chain_data: pd.DataFrame,
                                 current_date: datetime,
                                 is_long: bool = True) -> List[Dict]:
        """Generate straddle signals based on stock and option data.

        Args:
            stock_data: DataFrame with stock price data
            option_chain_data: DataFrame with option chain data
            current_date: Current date for signal generation
            is_long: If True, generate long straddle signals; if False, generate short straddle signals

        Returns:
            List of straddle signal dictionaries
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

        # Find ATM (at-the-money) strike - closest to current stock price
        if 'strike_price' in exp_options.columns:
            exp_options['strike_distance'] = abs(exp_options['strike_price'] - current_stock_price)
            atm_options = exp_options.nsmallest(1, 'strike_distance')

            if not atm_options.empty:
                atm_strike = atm_options.iloc[0]['strike_price']

                # Get call and put options at ATM strike
                call_options = exp_options[
                    (exp_options['strike_price'] == atm_strike) &
                    (exp_options['option_type'] == 'call')
                ]

                put_options = exp_options[
                    (exp_options['strike_price'] == atm_strike) &
                    (exp_options['option_type'] == 'put')
                ]

                if not call_options.empty and not put_options.empty:
                    call_option = call_options.iloc[0]
                    put_option = put_options.iloc[0]

                    # Calculate straddle cost (for long straddle) or credit (for short straddle)
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
                        straddle_price = call_price + put_price

                        # Calculate position size based on risk limits
                        contract_multiplier = 100  # Standard option contract multiplier
                        max_dollar_risk = straddle_price * contract_multiplier  # Cost of 1 straddle contract

                        if max_dollar_risk > 0:
                            # Calculate how many straddles we can trade based on risk limit
                            # This is simplified - in practice would need portfolio value
                            quantity = 1  # Start with 1 contract for safety

                            # Calculate breakeven points
                            breakeven_upper = atm_strike + straddle_price
                            breakeven_lower = atm_strike - straddle_price

                            # For long straddle: max loss is the premium paid, max profit is unlimited
                            # For short straddle: max profit is the premium received, max loss is unlimited
                            if is_long:
                                max_loss = straddle_price * contract_multiplier * quantity
                                max_profit = float('inf')  # Unlimited upside
                            else:
                                max_loss = float('inf')  # Unlimited downside
                                max_profit = straddle_price * contract_multiplier * quantity

                            signal = {
                                'signal_type': 'long_straddle' if is_long else 'short_straddle',
                                'underlying_symbol': self.underlying_symbol,
                                'expiration_date': target_expiration,
                                'strike_price': atm_strike,
                                'call_symbol': call_option.get('symbol', ''),
                                'put_symbol': put_option.get('symbol', ''),
                                'quantity': quantity,
                                'entry_price': straddle_price,
                                'max_loss': max_loss,
                                'max_profit': max_profit,
                                'breakeven_upper': breakeven_upper,
                                'breakeven_lower': breakeven_lower,
                                'current_stock_price': current_stock_price,
                                'straddle_price': straddle_price,
                                'is_long': is_long,
                                'timestamp': current_date
                            }

                            signals.append(signal)
                            logger.info(f"Generated {'long' if is_long else 'short'} straddle signal: "
                                      f"{self.underlying_symbol} {atm_strike} straddle expiring {target_expiration}")

        return signals

    def calculate_straddle_pnl(self,
                              position: Straddle,
                              current_stock_price: float,
                              current_date: datetime) -> float:
        """Calculate current P&L for a straddle position.

        Args:
            position: Straddle position object
            current_stock_price: Current price of the underlying stock
            current_date: Current date

        Returns:
            Current P&L in dollars
        """
        # This is a simplified P&L calculation
        # In practice, would need current option prices to calculate accurately

        # For demonstration, using intrinsic value approximation
        call_intrinsic = max(0, current_stock_price - position.strike_price)
        put_intrinsic = max(0, position.strike_price - current_stock_price)

        # Current straddle value (approximation)
        current_straddle_value = call_intrinsic + put_intrinsic

        # P&L = (current value - entry price) * quantity * multiplier
        # For long straddle: profit when stock moves significantly in either direction
        # For short straddle: profit when stock stays near strike price
        pnl = (current_straddle_value - position.entry_price) * position.call_quantity * 100

        # Adjust for short straddle (we sold the straddle, so P&L is inverted)
        if not position.is_long:
            pnl = -pnl

        return pnl
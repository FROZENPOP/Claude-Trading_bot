"""Butterfly strategy implementation for long and short butterflies."""

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
class Butterfly:
    """Represents a butterfly position."""
    underlying_symbol: str
    expiration_date: str
    lower_strike: float  # Lower strike price
    middle_strike: float  # Middle strike price (ATM)
    upper_strike: float  # Upper strike price
    quantity: int  # Number of butterfly contracts
    entry_date: datetime
    entry_price: float  # Net debit (for long butterfly) or credit (for short butterfly)
    max_loss: float     # For long butterfly: entry price * contract multiplier * quantity
                       # For short butterfly: entry price * contract multiplier * quantity
    max_profit: float   # For long butterfly: (middle_strike - lower_strike - entry_price) * multiplier * quantity
                       # For short butterfly: (upper_strike - middle_strike - entry_price) * multiplier * quantity
    is_long: bool       # True for long butterfly, False for short butterfly


class ButterflyStrategy:
    """Butterfly strategy for options trading."""

    def __init__(self, underlying_symbol: str, max_risk_per_trade: float = 0.02):
        """Initialize butterfly strategy.

        Args:
            underlying_symbol: The underlying stock symbol (e.g., 'AAPL')
            max_risk_per_trade: Maximum risk per trade as fraction of portfolio (default 2%)
        """
        self.underlying_symbol = underlying_symbol
        self.max_risk_per_trade = max_risk_per_trade
        self.option_pricing_model = OptionPricingModel()
        self.signal_generator = SignalGenerator()

    def generate_butterfly_signals(self,
                                  stock_data: pd.DataFrame,
                                  option_chain_data: pd.DataFrame,
                                  current_date: datetime,
                                  is_long: bool = True) -> List[Dict]:
        """Generate butterfly signals based on stock and option data.

        Args:
            stock_data: DataFrame with stock price data
            option_chain_data: DataFrame with option chain data
            current_date: Current date for signal generation
            is_long: If True, generate long butterfly signals; if False, generate short butterfly signals

        Returns:
            List of butterfly signal dictionaries
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
                middle_strike = atm_options.iloc[0]['strike_price']

                # Get all available strikes
                available_strikes = sorted(exp_options['strike_price'].unique())

                # Find lower and upper strikes for butterfly
                # Lower strike: closest strike below middle
                # Upper strike: closest strike above middle
                lower_strikes = [s for s in available_strikes if s < middle_strike]
                upper_strikes = [s for s in available_strikes if s > middle_strike]

                if lower_strikes and upper_strikes:
                    lower_strike = lower_strikes[-1]  # Highest strike below middle
                    upper_strike = upper_strikes[0]   # Lowest strike above middle

                    # Get option prices for all three strikes
                    lower_options = exp_options[(exp_options['strike_price'] == lower_strike) & (exp_options['option_type'] == 'call')]
                    middle_options = exp_options[(exp_options['strike_price'] == middle_strike) & (exp_options['option_type'] == 'call')]
                    upper_options = exp_options[(exp_options['strike_price'] == upper_strike) & (exp_options['option_type'] == 'call')]

                    # Also check put options if call options not available
                    if lower_options.empty:
                        lower_options = exp_options[(exp_options['strike_price'] == lower_strike) & (exp_options['option_type'] == 'put')]
                    if middle_options.empty:
                        middle_options = exp_options[(exp_options['strike_price'] == middle_strike) & (exp_options['option_type'] == 'put')]
                    if upper_options.empty:
                        upper_options = exp_options[(exp_options['strike_price'] == upper_strike) & (exp_options['option_type'] == 'put')]

                    if not lower_options.empty and not middle_options.empty and not upper_options.empty:
                        lower_option = lower_options.iloc[0]
                        middle_option = middle_options.iloc[0]
                        upper_option = upper_options.iloc[0]

                        # Get option prices
                        lower_price = lower_option.get('last_price', lower_option.get('bid_price', 0))
                        middle_price = middle_option.get('last_price', middle_option.get('bid_price', 0))
                        upper_price = upper_option.get('last_price', upper_option.get('bid_price', 0))

                        if lower_price <= 0 or middle_price <= 0 or upper_price <= 0:
                            # Try using mid-price if last price not available
                            def get_mid_price(option):
                                bid = option.get('bid_price', 0)
                                ask = option.get('ask_price', 0)
                                if bid > 0 and ask > 0:
                                    return (bid + ask) / 2
                                return option.get('last_price', 0)

                            lower_price = get_mid_price(lower_option)
                            middle_price = get_mid_price(middle_option)
                            upper_price = get_mid_price(upper_option)

                        if lower_price > 0 and middle_price > 0 and upper_price > 0:
                            # For butterfly: Buy 1 lower strike, Sell 2 middle strikes, Buy 1 upper strike
                            # Cost = lower_price - 2*middle_price + upper_price
                            butterfly_price = lower_price - (2 * middle_price) + upper_price

                            # Only proceed if we have a valid debit (for long butterfly) or credit (for short butterfly)
                            if is_long and butterfly_price > 0:
                                # Long butterfly: debit strategy
                                entry_price = butterfly_price
                                contract_multiplier = 100  # Standard option contract multiplier
                                max_dollar_risk = entry_price * contract_multiplier  # Cost of 1 butterfly contract

                                if max_dollar_risk > 0:
                                    quantity = 1  # Start with 1 contract for safety

                                    # Calculate max profit and loss
                                    max_loss = entry_price * contract_multiplier * quantity
                                    max_profit = ((middle_strike - lower_strike) - entry_price) * contract_multiplier * quantity

                                    signal = {
                                        'signal_type': 'long_butterfly',
                                        'underlying_symbol': self.underlying_symbol,
                                        'expiration_date': target_expiration,
                                        'lower_strike': lower_strike,
                                        'middle_strike': middle_strike,
                                        'upper_strike': upper_strike,
                                        'lower_symbol': lower_option.get('symbol', ''),
                                        'middle_symbol': middle_option.get('symbol', ''),
                                        'upper_symbol': upper_option.get('symbol', ''),
                                        'quantity': quantity,
                                        'entry_price': entry_price,
                                        'max_loss': max_loss,
                                        'max_profit': max_profit,
                                        'current_stock_price': current_stock_price,
                                        'butterfly_price': butterfly_price,
                                        'is_long': is_long,
                                        'timestamp': current_date
                                    }

                                    signals.append(signal)
                                    logger.info(f"Generated long butterfly signal: "
                                              f"{self.underlying_symbol} {lower_strike}/{middle_strike}/{upper_strike} butterfly expiring {target_expiration}")

                            elif not is_long and butterfly_price < 0:
                                # Short butterfly: credit strategy (we do the opposite: Sell 1 lower, Buy 2 middle, Sell 1 upper)
                                entry_price = abs(butterfly_price)  # Positive value for credit received
                                contract_multiplier = 100  # Standard option contract multiplier
                                max_dollar_risk = entry_price * contract_multiplier  # Risk of 1 butterfly contract

                                if max_dollar_risk > 0:
                                    quantity = 1  # Start with 1 contract for safety

                                    # Calculate max profit and loss
                                    max_profit = entry_price * contract_multiplier * quantity
                                    max_loss = ((upper_strike - middle_strike) - entry_price) * contract_multiplier * quantity

                                    signal = {
                                        'signal_type': 'short_butterfly',
                                        'underlying_symbol': self.underlying_symbol,
                                        'expiration_date': target_expiration,
                                        'lower_strike': lower_strike,
                                        'middle_strike': middle_strike,
                                        'upper_strike': upper_strike,
                                        'lower_symbol': lower_option.get('symbol', ''),
                                        'middle_symbol': middle_option.get('symbol', ''),
                                        'upper_symbol': upper_option.get('symbol', ''),
                                        'quantity': quantity,
                                        'entry_price': entry_price,
                                        'max_loss': max_loss,
                                        'max_profit': max_profit,
                                        'current_stock_price': current_stock_price,
                                        'butterfly_price': abs(butterfly_price),  # Store as positive
                                        'is_long': is_long,
                                        'timestamp': current_date
                                    }

                                    signals.append(signal)
                                    logger.info(f"Generated short butterfly signal: "
                                              f"{self.underlying_symbol} {lower_strike}/{middle_strike}/{upper_strike} butterfly expiring {target_expiration}")
                    else:
                        logger.warning("Could not find all three strikes for butterfly")
                else:
                    logger.warning("Insufficient strikes available for butterfly")
            else:
                logger.warning("No ATM options found")
        else:
            logger.warning("Option chain data missing strike_price column")

        return signals

    def calculate_butterfly_pnl(self,
                               position: Butterfly,
                               current_stock_price: float,
                               current_date: datetime) -> float:
        """Calculate current P&L for a butterfly position.

        Args:
            position: Butterfly position object
            current_stock_price: Current price of the underlying stock
            current_date: Current date

        Returns:
            Current P&L in dollars
        """
        # This is a simplified P&L calculation
        # In practice, would need current option prices to calculate accurately

        # For demonstration, using intrinsic value approximation
        def calculate_intrinsic_value(stock_price, strike_price, option_type):
            if option_type == 'call':
                return max(0, stock_price - strike_price)
            else:  # put
                return max(0, strike_price - stock_price)

        # We'll assume we're using calls for simplicity (can be extended to puts)
        lower_intrinsic = calculate_intrinsic_value(current_stock_price, position.lower_strike, 'call')
        middle_intrinsic = calculate_intrinsic_value(current_stock_price, position.middle_strike, 'call')
        upper_intrinsic = calculate_intrinsic_value(current_stock_price, position.upper_strike, 'call')

        # Current butterfly value (approximation)
        # Long butterfly: +1 lower -2 middle +1 upper
        current_butterfly_value = lower_intrinsic - (2 * middle_intrinsic) + upper_intrinsic

        # P&L = (current value - entry price) * quantity * multiplier
        pnl = (current_butterfly_value - position.entry_price) * position.quantity * 100

        # Adjust for short butterfly (we sold the butterfly, so P&L is inverted)
        if not position.is_long:
            pnl = -pnl

        return pnl
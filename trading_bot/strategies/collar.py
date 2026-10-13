"""Collar strategy implementation for protective collars."""

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
class Collar:
    """Represents a collar position."""
    underlying_symbol: str
    expiration_date: str
    stock_quantity: int  # Number of shares owned
    put_strike: float    # Strike price for protective put
    call_strike: float   # Strike price for covered call (call_strike > put_strike)
    put_quantity: int    # Number of put contracts
    call_quantity: int   # Number of call contracts
    entry_date: datetime
    entry_price: float   # Net debit/credit (put premium - call premium)
    max_loss: float      # Maximum possible loss
    max_profit: float    # Maximum possible profit
    is_long: bool        # Always True for collar (protective strategy)


class CollarStrategy:
    """Collar strategy for options trading."""

    def __init__(self, underlying_symbol: str, max_risk_per_trade: float = 0.02):
        """Initialize collar strategy.

        Args:
            underlying_symbol: The underlying stock symbol (e.g., 'AAPL')
            max_risk_per_trade: Maximum risk per trade as fraction of portfolio (default 2%)
        """
        self.underlying_symbol = underlying_symbol
        self.max_risk_per_trade = max_risk_per_trade
        self.option_pricing_model = OptionPricingModel()
        self.signal_generator = SignalGenerator()

    def generate_collar_signals(self,
                               stock_data: pd.DataFrame,
                               option_chain_data: pd.DataFrame,
                               current_date: datetime) -> List[Dict]:
        """Generate collar signals based on stock and option data.

        Args:
            stock_data: DataFrame with stock price data
            option_chain_data: DataFrame with option chain data
            current_date: Current date for signal generation

        Returns:
            List of collar signal dictionaries
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

        # Find OTM put strike (below current price) and OTM call strike (above current price)
        # Typical collar: buy put at ~90-95% of current price, sell call at ~105-110% of current price
        put_target_price = current_stock_price * 0.90  # 10% OTM put
        call_target_price = current_stock_price * 1.10  # 10% OTM call

        if 'strike_price' in exp_options.columns:
            # Find closest put strike (below or near target)
            put_options = exp_options[exp_options['option_type'] == 'put'].copy()
            if not put_options.empty:
                put_options['strike_distance'] = abs(put_options['strike_price'] - put_target_price)
                # Filter to strikes at or below target (protective puts)
                put_options = put_options[put_options['strike_price'] <= put_target_price * 1.05]  # Allow 5% flexibility
                if not put_options.empty:
                    closest_put = put_options.nsmallest(1, 'strike_distance')
                    if not closest_put.empty:
                        put_strike = closest_put.iloc[0]['strike_price']
                        put_option = closest_put.iloc[0]
                    else:
                        logger.warning("No suitable put options found")
                        return signals
                else:
                    # If no OTM puts, use closest ATM put
                    put_options['strike_distance'] = abs(put_options['strike_price'] - put_target_price)
                    closest_put = put_options.nsmallest(1, 'strike_distance')
                    if not closest_put.empty:
                        put_strike = closest_put.iloc[0]['strike_price']
                        put_option = closest_put.iloc[0]
                    else:
                        logger.warning("No put options found")
                        return signals
            else:
                logger.warning("No put options found in chain")
                return signals

            # Find closest call strike (above or near target)
            call_options = exp_options[exp_options['option_type'] == 'call'].copy()
            if not call_options.empty:
                call_options['strike_distance'] = abs(call_options['strike_price'] - call_target_price)
                # Filter to strikes at or above target (covered calls)
                call_options = call_options[call_options['strike_price'] >= call_target_price * 0.95]  # Allow 5% flexibility
                if not call_options.empty:
                    closest_call = call_options.nsmallest(1, 'strike_distance')
                    if not closest_call.empty:
                        call_strike = closest_call.iloc[0]['strike_price']
                        call_option = closest_call.iloc[0]
                    else:
                        logger.warning("No suitable call options found")
                        return signals
                else:
                    # If no OTM calls, use closest ATM call
                    call_options['strike_distance'] = abs(call_options['strike_price'] - call_target_price)
                    closest_call = call_options.nsmallest(1, 'strike_distance')
                    if not closest_call.empty:
                        call_strike = closest_call.iloc[0]['strike_price']
                        call_option = closest_call.iloc[0]
                    else:
                        logger.warning("No call options found")
                        return signals
            else:
                logger.warning("No call options found in chain")
                return signals

            # Ensure call strike is greater than put strike (valid collar)
            if call_strike <= put_strike:
                logger.warning(f"Invalid collar: call strike ({call_strike}) <= put strike ({put_strike})")
                return signals

            # Get option prices
            put_price = put_option.get('last_price', put_option.get('bid_price', 0))
            call_price = call_option.get('last_price', call_option.get('bid_price', 0))

            if put_price <= 0 or call_price <= 0:
                # Try using mid-price if last price not available
                def get_mid_price(option):
                    bid = option.get('bid_price', 0)
                    ask = option.get('ask_price', 0)
                    if bid > 0 and ask > 0:
                        return (bid + ask) / 2
                    return option.get('last_price', 0)

                put_price = get_mid_price(put_option)
                call_price = get_mid_price(call_option)

            if put_price > 0 and call_price > 0:
                # For collar: Buy put, Sell call
                # Cost = put_price - call_price (can be debit or credit)
                collar_price = put_price - call_price

                # Calculate position size based on stock shares
                # Each option contract typically covers 100 shares
                stock_quantity = 100  # Start with 100 shares (1 contract)
                put_quantity = 1      # 1 put contract
                call_quantity = 1     # 1 call contract

                # Calculate max loss and max profit
                if collar_price >= 0:  # Debit collar
                    # Max loss = (current_stock_price - put_strike) * stock_quantity + collar_price * 100
                    # Max profit = (call_strike - current_stock_price) * stock_quantity - collar_price * 100
                    max_loss = max(0, (current_stock_price - put_strike) * stock_quantity) + (collar_price * 100)
                    max_profit = max(0, (call_strike - current_stock_price) * stock_quantity) - (collar_price * 100)
                else:  # Credit collar
                    # Max loss = (current_stock_price - put_strike) * stock_quantity + abs(collar_price) * 100
                    # Max profit = (call_strike - current_stock_price) * stock_quantity + abs(collar_price) * 100
                    max_loss = max(0, (current_stock_price - put_strike) * stock_quantity) + (abs(collar_price) * 100)
                    max_profit = max(0, (call_strike - current_stock_price) * stock_quantity) + (abs(collar_price) * 100)

                # Ensure we have reasonable values
                if max_loss >= 0 and max_profit >= 0:
                    signal = {
                        'signal_type': 'collar',
                        'underlying_symbol': self.underlying_symbol,
                        'expiration_date': target_expiration,
                        'stock_quantity': stock_quantity,
                        'put_strike': put_strike,
                        'call_strike': call_strike,
                        'put_symbol': put_option.get('symbol', ''),
                        'call_symbol': call_option.get('symbol', ''),
                        'put_quantity': put_quantity,
                        'call_quantity': call_quantity,
                        'entry_price': collar_price,  # Net debit (positive) or credit (negative)
                        'max_loss': max_loss,
                        'max_profit': max_profit,
                        'current_stock_price': current_stock_price,
                        'collar_price': collar_price,
                        'is_long': True,  # Collar is always a protective strategy
                        'timestamp': current_date
                    }

                    signals.append(signal)
                    logger.info(f"Generated collar signal: "
                              f"{self.underlying_symbol} {stock_quantity} shares with "
                              f"put {put_strike}/call {call_strike} collar expiring {target_expiration}")

        return signals

    def calculate_collar_pnl(self,
                            position: Collar,
                            current_stock_price: float,
                            current_date: datetime) -> float:
        """Calculate current P&L for a collar position.

        Args:
            position: Collar position object
            current_stock_price: Current price of the underlying stock
            current_date: Current date

        Returns:
            Current P&L in dollars
        """
        # For collar: Long stock + Long put + Short call

        # Stock P&L
        # Assuming we entered at current_stock_price (simplified)
        stock_pnl = (current_stock_price - position.current_stock_price) * position.stock_quantity

        # Put option P&L (long put)
        put_intrinsic = max(0, position.put_strike - current_stock_price)
        put_pnl = (put_intrinsic - position.entry_price if position.entry_price > 0 else put_intrinsic + abs(position.entry_price)) * position.put_quantity * 100
        # Simplified: if we paid for put (debit), P&L = (current_value - entry_price) * quantity
        # If we received credit for put, P&L = (current_value + abs(entry_price)) * quantity

        # Call option P&L (short call)
        call_intrinsic = max(0, current_stock_price - position.call_strike)
        call_pnl = (position.entry_price if position.entry_price > 0 else -call_intrinsic) * position.call_quantity * 100
        # Simplified: if we sold call for credit, P&L = entry_price - max(0, stock_price - strike)

        # Total P&L
        total_pnl = stock_pnl + put_pnl + call_pnl

        return total_pnl
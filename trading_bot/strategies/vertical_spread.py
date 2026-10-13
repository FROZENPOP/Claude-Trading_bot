"""Vertical spread strategy implementation for bull call and bear put spreads."""

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
class VerticalSpread:
    """Represents a vertical spread position."""
    underlying_symbol: str
    expiration_date: str
    long_strike: float
    short_strike: float
    option_type: str  # 'call' for bull call spread, 'put' for bear put spread
    long_quantity: int
    short_quantity: int  # Should be same as long_quantity for ratio spread
    entry_date: datetime
    entry_price: float  # Net debit (for bull call) or credit (for bear put)
    max_loss: float
    max_profit: float
    breakeven: float

    def __post_init__(self):
        """Calculate derived values after initialization."""
        quantity = abs(self.long_quantity)
        if self.option_type == 'call':
            # Bull call spread: long lower strike, short higher strike
            self.max_profit = ((self.short_strike - self.long_strike) * 100 * quantity) - (abs(self.entry_price) * 100 * quantity)
            self.breakeven = self.long_strike + (abs(self.entry_price) / 100)
        else:  # put
            # Bear put spread: long higher strike, short lower strike
            self.max_profit = ((self.long_strike - self.short_strike) * 100 * quantity) - (abs(self.entry_price) * 100 * quantity)
            self.breakeven = self.long_strike - (abs(self.entry_price) / 100)

        self.max_loss = abs(self.entry_price) * 100 * quantity  # Initial debit paid


@dataclass
class SpreadSignal:
    """Represents a signal to enter a vertical spread."""
    underlying_symbol: str
    signal_type: str  # 'bullish' or 'bearish'
    signal_strength: float  # 0-1 scale
    recommended_dte: List[int]  # Preferred days to expiration
    recommended_delta_range: Tuple[float, float]  # (min_delta, max_delta)
    spread_width_preference: str  # 'narrow', 'medium', 'wide' or specific dollar amount
    timestamp: datetime


class VerticalSpreadStrategy:
    """Vertical spread strategy that generates option trades from underlying signals."""

    def __init__(
        self,
        underlying_symbol: Optional[str] = None,
        signal_generator: Optional[SignalGenerator] = None,
        max_risk_per_trade: float = 0.02,  # 2% of portfolio per trade
        preferred_dte: List[int] = [21, 30, 45, 60],
        preferred_delta_range: Tuple[float, float] = (0.4, 0.6),
        max_spread_width: float = 10.0,  # Maximum spread width in dollars
        risk_free_rate: float = 0.05,
        max_contracts_per_trade: int = 10  # Maximum number of contracts per trade
    ):
        """Initialize vertical spread strategy.

        Args:
            underlying_symbol: Underlying stock symbol (e.g., 'AAPL')
            signal_generator: Underlying signal generator (if None, creates default)
            max_risk_per_trade: Maximum risk per trade as fraction of portfolio
            preferred_dte: Preferred days to expiration for options
            preferred_delta_range: Preferred delta range for long leg
            max_spread_width: Maximum spread width in dollars
            risk_free_rate: Risk-free rate for pricing models
            max_contracts_per_trade: Maximum number of contracts per trade
        """
        self.underlying_symbol = underlying_symbol
        self.signal_generator = signal_generator or SignalGenerator()
        self.max_risk_per_trade = max_risk_per_trade
        self.preferred_dte = preferred_dte
        self.preferred_delta_range = preferred_delta_range
        self.max_spread_width = max_spread_width
        self.risk_free_rate = risk_free_rate
        self.max_contracts_per_trade = max_contracts_per_trade
        self.pricing_model = OptionPricingModel(risk_free_rate)

        logger.info(f"Vertical spread strategy initialized for {underlying_symbol}")

    def generate_spread_signals(
        self,
        market_data: pd.DataFrame,
        option_chain: pd.DataFrame,
        current_date: Optional[datetime] = None
    ) -> List[SpreadSignal]:
        """Generate vertical spread signals based on underlying data and option chain.

        Args:
            market_data: DataFrame with underlying price and indicator data
            option_chain: DataFrame with current option chain data
            current_date: Current date (None for today)

        Returns:
            List of SpreadSignal objects
        """
        if current_date is None:
            current_date = datetime.now()
        # Convert to date object if it's a datetime or has a date method (like pandas Timestamp)
        if isinstance(current_date, datetime):
            current_date = current_date.date()
        elif hasattr(current_date, 'date'):
            current_date = current_date.date()

        signals = []

        # Get underlying signal
        underlying_signal = self.signal_generator.get_signal(market_data, current_date)

        if underlying_signal is None or underlying_signal.signal_strength < 0.3:
            logger.debug(f"Underlying signal too weak: {underlying_signal}")
            return signals

        # Determine spread type based on signal
        if underlying_signal.signal_type == 'bullish':
            spread_signals = self._generate_bull_call_signals(
                underlying_signal, option_chain, market_data, current_date
            )
        elif underlying_signal.signal_type == 'bearish':
            spread_signals = self._generate_bear_put_signals(
                underlying_signal, option_chain, market_data, current_date
            )
        else:
            logger.debug(f"Neutral signal received: {underlying_signal.signal_type}")
            return signals

        signals.extend(spread_signals)
        return signals

    def _generate_bull_call_signals(
        self,
        signal,
        option_chain: pd.DataFrame,
        market_data: pd.DataFrame,
        current_date: datetime
    ) -> List[SpreadSignal]:
        """Generate bull call spread signals."""
        spread_signals = []

        # Filter option chain for calls
        calls = option_chain[
            (option_chain['option_type'] == 'call') &
            option_chain['expiration_date'].notna()
        ].copy()

        if calls.empty:
            logger.warning("No call options found in chain")
            return spread_signals

        # Calculate days to expiration for each option
        calls['days_to_exp'] = calls['expiration_date'].apply(
            lambda x: (datetime.strptime(x, '%Y-%m-%d').date() - current_date).days
        )

        # Filter to preferred DTE range
        calls = calls[
            calls['days_to_exp'].isin(self.preferred_dte) &
            (calls['days_to_exp'] > 0)  # Not expired
        ]

        if calls.empty:
            logger.debug(f"No calls found in preferred DTE range: {self.preferred_dte}")
            return spread_signals

        # Get underlying price
        underlying_price = self._get_underlying_price(market_data=market_data, current_date=current_date)
        if underlying_price is None:
            logger.warning("Could not get underlying price")
            return spread_signals

        # For each preferred DTE, find suitable strikes
        for dte in self.preferred_dte:
            dte_calls = calls[calls['days_to_exp'] == dte].copy()

            if dte_calls.empty:
                continue

            # Get unique actual strikes available for this DTE
            available_strikes = sorted(dte_calls['strike_price'].unique())

            if len(available_strikes) < 2:
                continue

            # Try to find strikes within preferred delta range
            # For simplicity, we'll use strikes near the money if Greeks not available
            atm_strike = round(underlying_price)  # At-the-money strike

            # Generate candidate spreads from actual available strikes
            for i, long_strike in enumerate(available_strikes):
                # For bull call: long call (lower strike), short call (higher strike)
                # We want: long_strike < short_strike

                # Look for valid short strikes (higher strikes) in the remaining available strikes
                for j in range(i + 1, len(available_strikes)):
                    short_strike = available_strikes[j]
                    width = short_strike - long_strike

                    # Check if width is within acceptable range
                    if width > self.max_spread_width:
                        # Since strikes are sorted, further strikes will only increase width
                        break

                    if width < 1.0:  # Minimum width check (avoid too narrow spreads)
                        continue

                    # Check if both strikes exist in the chain (they do, since we got them from available_strikes)
                    # Calculate approximate entry price using mid prices
                    long_mid = self._get_option_mid_price(
                        dte_calls, 'call', long_strike, current_date
                    )
                    short_mid = self._get_option_mid_price(
                        dte_calls, 'call', short_strike, current_date
                    )

                    if long_mid is not None and short_mid is not None:
                        net_debit = short_mid - long_mid  # Debit for bull call (we pay more for lower strike call)

                        # Only consider if it's a debit spread (we pay to enter)
                        if net_debit > 0:
                            spread_signal = SpreadSignal(
                                underlying_symbol=self.underlying_symbol,
                                signal_type='bullish',
                                signal_strength=signal.signal_strength,
                                recommended_dte=[dte],
                                recommended_delta_range=self.preferred_delta_range,
                                spread_width_preference=f"{width}",
                                timestamp=current_date
                            )
                            # Store additional info in signal for later use
                            spread_signal.__dict__.update({
                                'long_strike': long_strike,
                                'short_strike': short_strike,
                                'option_type': 'call',
                                'underlying_price': underlying_price,
                                'net_debit': net_debit,
                                'days_to_exp': dte
                            })
                            spread_signals.append(spread_signal)

        logger.info(f"Generated {len(spread_signals)} bull call spread signals")
        return spread_signals

    def _generate_bear_put_signals(
        self,
        signal,
        option_chain: pd.DataFrame,
        market_data: pd.DataFrame,
        current_date: datetime
    ) -> List[SpreadSignal]:
        """Generate bear put spread signals."""
        spread_signals = []

        # Filter option chain for puts
        puts = option_chain[
            (option_chain['option_type'] == 'put') &
            option_chain['expiration_date'].notna()
        ].copy()

        if puts.empty:
            logger.warning("No put options found in chain")
            return spread_signals

        # Calculate days to expiration for each option
        puts['days_to_exp'] = puts['expiration_date'].apply(
            lambda x: (datetime.strptime(x, '%Y-%m-%d').date() - current_date).days
        )

        # Filter to preferred DTE range
        puts = puts[
            puts['days_to_exp'].isin(self.preferred_dte) &
            (puts['days_to_exp'] > 0)  # Not expired
        ]

        if puts.empty:
            logger.debug(f"No puts found in preferred DTE range: {self.preferred_dte}")
            return spread_signals

        # Get underlying price
        underlying_price = self._get_underlying_price(market_data=market_data, current_date=current_date)
        if underlying_price is None:
            logger.warning("Could not get underlying price")
            return spread_signals

        # For each preferred DTE, find suitable strikes
        for dte in self.preferred_dte:
            dte_puts = puts[puts['days_to_exp'] == dte].copy()

            if dte_puts.empty:
                continue

            # Get unique actual strikes available for this DTE
            available_strikes = sorted(dte_puts['strike_price'].unique())

            if len(available_strikes) < 2:
                continue

            # Try to find strikes within preferred delta range
            atm_strike = round(underlying_price)  # At-the-money strike

            # Generate candidate spreads from actual available strikes
            for i, long_strike in enumerate(available_strikes):
                # For bear put: long put (higher strike), short put (lower strike)
                # We want: long_strike > short_strike

                # Look for valid short strikes (lower strikes) in the earlier available strikes
                for j in range(i):
                    short_strike = available_strikes[j]
                    width = long_strike - short_strike

                    # Check if width is within acceptable range
                    if width > self.max_spread_width:
                        # Since we're going backwards in strikes, further decreases will only increase width
                        continue

                    if width < 1.0:  # Minimum width check (avoid too narrow spreads)
                        continue

                    # Check if both strikes exist in the chain (they do, since we got them from available_strikes)
                    # Calculate approximate entry price using mid prices
                    long_mid = self._get_option_mid_price(
                        dte_puts, 'put', long_strike, current_date
                    )
                    short_mid = self._get_option_mid_price(
                        dte_puts, 'put', short_strike, current_date
                    )

                    if long_mid is not None and short_mid is not None:
                        net_debit = long_mid - short_mid  # Debit for bear put (we pay more for higher strike put)

                        # Only consider if it's a debit spread
                        if net_debit > 0:
                            spread_signal = SpreadSignal(
                                underlying_symbol=self.underlying_symbol,
                                signal_type='bearish',
                                signal_strength=signal.signal_strength,
                                recommended_dte=[dte],
                                recommended_delta_range=self.preferred_delta_range,
                                spread_width_preference=f"{width}",
                                timestamp=current_date
                            )
                            # Store additional info in signal for later use
                            spread_signal.__dict__.update({
                                'long_strike': long_strike,
                                'short_strike': short_strike,
                                'option_type': 'put',
                                'underlying_price': underlying_price,
                                'net_debit': net_debit,
                                'days_to_exp': dte
                            })
                            spread_signals.append(spread_signal)

        logger.info(f"Generated {len(spread_signals)} bear put spread signals")
        return spread_signals

    def _get_underlying_price(
        self,
        market_data: Optional[pd.DataFrame],
        current_date: datetime
    ) -> Optional[float]:
        """Get current underlying price from market data or return placeholder."""
        if market_data is not None and not market_data.empty:
            # Get the most recent price
            if 'adjusted_close' in market_data.columns:
                return float(market_data['adjusted_close'].iloc[-1])
            elif 'close' in market_data.columns:
                return float(market_data['close'].iloc[-1])

        # Fallback - in practice, this would come from real-time data
        logger.warning("Unable to get underlying price - returning None")
        return None

    def _get_option_mid_price(
        self,
        option_df: pd.DataFrame,
        option_type: str,
        strike_price: float,
        current_date: datetime
    ) -> Optional[float]:
        """Get mid price for a specific option strike and type."""
        # Find option matching strike and type
        matching_options = option_df[
            (option_df['option_type'] == option_type) &
            (abs(option_df['strike_price'] - strike_price) < 0.25)
        ]

        if matching_options.empty:
            return None

        # Use the first match (should be only one per strike/type/expiration)
        option = matching_options.iloc[0]

        # Calculate mid price
        bid = option.get('bid_price')
        ask = option.get('ask_price')

        if bid is not None and ask is not None:
            return (bid + ask) / 2
        elif option.get('last_price') is not None:
            return option['last_price']
        else:
            return None

    def create_vertical_spread(
        self,
        signal: SpreadSignal,
        portfolio_value: float,
        current_date: Optional[datetime] = None
    ) -> Optional[VerticalSpread]:
        """Create a vertical spread position from a signal.

        Args:
            signal: SpreadSignal containing trade details
            portfolio_value: Current portfolio value for position sizing
            current_date: Current date (None for today)

        Returns:
            VerticalSpread object or None if cannot create
        """
        if current_date is None:
            current_date = datetime.now()

        # Extract signal details
        underlying_symbol = signal.underlying_symbol
        long_strike = getattr(signal, 'long_strike', None)
        short_strike = getattr(signal, 'short_strike', None)
        option_type = getattr(signal, 'option_type', None)
        net_debit = getattr(signal, 'net_debit', None)
        days_to_exp = getattr(signal, 'days_to_exp', None)

        if None in [long_strike, short_strike, option_type, net_debit, days_to_exp]:
            logger.error("Missing required signal information to create spread")
            return None

        # Calculate maximum risk allowed for this trade
        max_risk_dollars = portfolio_value * self.max_risk_per_trade

        # Calculate quantity based on risk
        risk_per_spread = net_debit * 100  # Cost per spread (1 contract each leg)
        if risk_per_spread <= 0:
            logger.error(f"Invalid risk per spread: {risk_per_spread}")
            return None

        max_quantity = int(max_risk_dollars / risk_per_spread)

        if max_quantity < 1:
            logger.warning(f"Calculated quantity is less than 1: {max_quantity}")
            return None

        # Use minimum of 1 contract or calculated max (respecting max_contracts_per_trade limit)
        quantity = max(1, min(max_quantity, self.max_contracts_per_trade))

        # Calculate actual risk
        actual_risk = quantity * net_debit * 100

        # Create the spread
        spread = VerticalSpread(
            underlying_symbol=underlying_symbol,
            expiration_date=(current_date + timedelta(days=days_to_exp)).strftime('%Y-%m-%d'),
            long_strike=long_strike,
            short_strike=short_strike,
            option_type=option_type,
            long_quantity=quantity if option_type == 'call' else quantity,  # Long is positive
            short_quantity=-quantity if option_type == 'call' else -quantity,  # Short is negative
            entry_date=current_date,
            entry_price=net_debit,  # Net debit (positive for debit spread)
            max_loss=actual_risk,
            max_profit=0,  # Will be calculated in __post_init__
            breakeven=0    # Will be calculated in __post_init__
        )

        logger.info(
            f"Created {option_type} vertical spread: "
            f"{quantity} contracts {underlying_symbol} "
            f"{long_strike}/{short_strike} exp {spread.expiration_date} "
            f"debit: ${net_debit:.2f} risk: ${actual_risk:.2f}"
        )

        return spread

    def exit_spread(
        self,
        spread: VerticalSpread,
        current_option_chain: pd.DataFrame,
        current_date: datetime
    ) -> Tuple[bool, float, str]:
        """Determine if a spread should be exited and calculate exit value.

        Args:
            spread: Current vertical spread position
            current_option_chain: Current option chain data
            current_date: Current date

        Returns:
            Tuple of (should_exit, exit_price, reason)
        """
        # Check if expired
        exp_date = datetime.strptime(spread.expiration_date, '%Y-%m-%d')
        days_to_exp = (exp_date - current_date).days

        if days_to_exp <= 0:
            # Option has expired - calculate settlement value
            return self._calculate_expiration_settlement(spread, current_option_chain, exp_date)

        # Get current mid prices for the spread legs
        long_mid = self._get_current_spread_leg_price(
            current_option_chain,
            spread.underlying_symbol,
            spread.expiration_date,
            abs(spread.long_strike),
            'call' if spread.option_type == 'call' else 'put',
            abs(spread.long_quantity)
        )

        short_mid = self._get_current_spread_leg_price(
            current_option_chain,
            spread.underlying_symbol,
            spread.expiration_date,
            abs(spread.short_strike),
            'call' if spread.option_type == 'call' else 'put',
            abs(spread.short_quantity)
        )

        if long_mid is None or short_mid is None:
            logger.warning(f"Could not get prices for spread exit calculation")
            return False, 0.0, "Missing price data"

        # Calculate current spread value
        if spread.option_type == 'call':
            # Bull call spread: long call, short call
            current_value = (long_mid - short_mid) * 100 * abs(spread.long_quantity)
        else:
            # Bear put spread: long put, short put
            current_value = (long_mid - short_mid) * 100 * abs(spread.long_quantity)

        # Calculate current P&L
        entry_cost = spread.entry_price * 100 * abs(spread.long_quantity)
        current_pnl = current_value - entry_cost

        # Exit conditions
        # 1. Take profit at 50% of max profit
        max_profit = spread.max_loss  # For debit spreads, max profit is width - debit
        if current_pnl >= 0.5 * max_profit:
            return True, current_value, f"Take profit target reached ({current_pnl:.2f})"

        # 2. Stop loss at 50% of max loss
        if current_pnl <= -0.5 * spread.max_loss:
            return True, current_value, f"Stop loss triggered ({current_pnl:.2f})"

        # 3. Time decay - exit if too close to expiration (e.g., 7 days)
        if days_to_exp <= 7:
            return True, current_value, f"Time decay exit ({days_to_exp} days to exp)"

        # 4. Underlying reversal signal (would need to check signal generator)
        # This would be implemented by checking for opposite signal

        return False, current_value, "Hold position"

    def _get_current_spread_leg_price(
        self,
        option_chain: pd.DataFrame,
        underlying_symbol: str,
        expiration_date: str,
        strike_price: float,
        option_type: str,
        quantity: int
    ) -> Optional[float]:
        """Get current mid price for a specific option leg."""
        # Filter option chain for the specific contract
        matching = option_chain[
            (option_chain['underlying_symbol'] == underlying_symbol) &
            (option_chain['expiration_date'] == expiration_date) &
            (abs(option_chain['strike_price'] - strike_price) < 0.25) &
            (option_chain['option_type'] == option_type)
        ]

        if matching.empty:
            return None

        # Use first match
        option = matching.iloc[0]

        # Calculate mid price
        bid = option.get('bid_price')
        ask = option.get('ask_price')

        if bid is not None and ask is not None:
            return (bid + ask) / 2
        elif option.get('last_price') is not None:
            return option['last_price']
        else:
            return None

    def _calculate_expiration_settlement(
        self,
        spread: VerticalSpread,
        option_chain: pd.DataFrame,
        expiration_date: datetime
    ) -> Tuple[bool, float, str]:
        """Calculate settlement value at expiration.

        Args:
            spread: Vertical spread position
            option_chain: Current option chain data (for underlying price)
            expiration_date: Expiration date

        Returns:
            Tuple of (should_exit, settlement_value, reason)
        """
        # At expiration, we need the underlying settlement price
        # Get it from market data if available
        underlying_settlement_price = self._get_underlying_price(option_chain, expiration_date)
        if underlying_settlement_price is None:
            # Fallback - try to get from recent market data
            logger.warning("Could not get underlying settlement price from option chain, using 0 as placeholder")
            underlying_settlement_price = 0.0  # Better to use 0 than a random placeholder

        if spread.option_type == 'call':
            # Bull call spread settlement
            # Long call: max(0, S - K_long)
            # Short call: max(0, S - K_short) * -1 (we are short)
            long_value = max(underlying_settlement_price - spread.long_strike, 0)
            short_value = -max(underlying_settlement_price - spread.short_strike, 0)
            spread_value = (long_value + short_value) * 100 * abs(spread.long_quantity)
        else:
            # Bear put spread settlement
            # Long put: max(0, K_long - S)
            # Short put: max(0, K_short - S) * -1 (we are short)
            long_value = max(spread.long_strike - underlying_settlement_price, 0)
            short_value = -max(spread.short_strike - underlying_settlement_price, 0)
            spread_value = (long_value + short_value) * 100 * abs(spread.long_quantity)

        entry_cost = spread.entry_price * 100 * abs(spread.long_quantity)
        pnl_at_expiration = spread_value - entry_cost

        logger.info(
            f"Spread expired. Underlying settlement: ${underlying_settlement_price:.2f}, "
            f"Spread value: ${spread_value:.2f}, Entry cost: ${entry_cost:.2f}, "
            f"P&L: ${pnl_at_expiration:.2f}"
        )

        return True, spread_value, f"Expired at {expiration_date.strftime('%Y-%m-%d')}"


if __name__ == "__main__":
    # Example usage
    import pandas as pd
    from datetime import datetime, timedelta

    # Create sample option chain data
    sample_data = []
    base_date = datetime.now() + timedelta(days=30)
    exp_date = base_date.strftime('%Y-%m-%d')

    # Generate sample calls and puts around ATM
    underlying_price = 150.0
    for strike in [145, 147.5, 150, 152.5, 155]:
        # Call option
        sample_data.append({
            'option_symbol': f'AAPL{base_date.strftime("%y%m%d")}C{int(strike*1000):08d}',
            'underlying_symbol': 'AAPL',
            'expiration_date': exp_date,
            'option_type': 'call',
            'strike_price': strike,
            'bid_price': max(0, underlying_price - strike + 2.5) * 0.8,
            'ask_price': max(0, underlying_price - strike + 2.5) * 0.9,
            'last_price': max(0, underlying_price - strike + 2.5) * 0.85,
            'volume': 100,
            'open_interest': 500
        })

        # Put option
        sample_data.append({
            'option_symbol': f'AAPL{base_date.strftime("%y%m%d")}P{int(strike*1000):08d}',
            'underlying_symbol': 'AAPL',
            'expiration_date': exp_date,
            'option_type': 'put',
            'strike_price': strike,
            'bid_price': max(0, strike - underlying_price + 2.5) * 0.8,
            'ask_price': max(0, strike - underlying_price + 2.5) * 0.9,
            'last_price': max(0, strike - underlying_price + 2.5) * 0.85,
            'volume': 100,
            'open_interest': 500
        })

    option_chain = pd.DataFrame(sample_data)

    # Create sample market data
    market_data = pd.DataFrame({
        'date': [datetime.now() - timedelta(days=i) for i in range(5, 0, -1)],
        'adjusted_close': [148, 149, 150, 151, 152],
        'short_ma': [149, 149.5, 150, 150.5, 151],
        'medium_ma': [148, 149, 150, 151, 152],
        'composite_score': [0.2, 0.3, 0.5, 0.6, 0.4]
    })

    # Initialize strategy
    strategy = VerticalSpreadStrategy('AAPL')

    # Generate signals
    signals = strategy.generate_spread_signals(market_data, option_chain)

    logger.info(f"Generated {len(signals)} spread signals")

    # Create a spread from first signal if available
    if signals:
        signal = signals[0]
        logger.info(f"Signal: {signal.signal_type} with strength {signal.signal_strength}")

        # Create spread
        spread = strategy.create_vertical_spread(signal, portfolio_value=100000)
        if spread:
            logger.info(f"Created spread: {spread}")

            # Check exit condition
            should_exit, exit_price, reason = strategy.exit_spread(
                spread, option_chain, datetime.now()
            )
            logger.info(f"Exit recommendation: {should_exit} - {reason}")
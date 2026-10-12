"""Calendar spread strategy implementation."""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from trading_bot.strategies.option_pricing import OptionPricingModel
from trading_bot.strategies.signals import SignalGenerator

logger = logging.getLogger(__name__)


@dataclass
class CalendarSpreadPosition:
    """Represents a calendar spread position."""
    underlying_symbol: str
    short_expiration: str   # Near-term expiration
    long_expiration: str    # Longer-term expiration
    strike_price: float     # Same strike for both options
    option_type: str        # 'call' or 'put'
    short_quantity: int     # Number of short-term contracts (negative)
    long_quantity: int      # Number of long-term contracts (positive)
    entry_date: datetime
    entry_price: float  # Net debit paid (positive for long calendar spread)
    max_profit: float
    max_loss: float

    def __post_init__(self):
        """Calculate derived values after initialization."""
        # For long calendar spread: short near-term option, long longer-term option
        # Same strike, same option type

        # Max loss = net debit paid
        self.max_loss = abs(self.entry_price) * 100 * abs(self.long_quantity)

        # Max profit is difficult to calculate precisely as it depends on
        # volatility term structure and underlying price at short-term expiration
        # Simplified approximation: max profit occurs when underlying price
        # is near strike at short-term expiration and long-term option has
        # maximum time value
        self.max_profit = self.max_loss * 2  # Rough approximation


class CalendarSpreadStrategy:
    """Calendar spread strategy for volatility term structure plays."""

    def __init__(
        self,
        underlying_symbol: str,
        signal_generator: Optional[SignalGenerator] = None,
        max_risk_per_trade: float = 0.02,  # 2% of portfolio per trade
        preferred_short_dte: List[int] = [7, 14, 21],   # Short-term: 1-3 weeks
        preferred_long_dte: List[int] = [30, 45, 60],   # Long-term: 1-2 months
        preferred_moneyness: Tuple[float, float] = (-0.05, 0.05),  # ATM options: ±5%
        risk_free_rate: float = 0.05,
        max_contracts_per_trade: int = 10  # Maximum number of contracts per trade
    ):
        """Initialize calendar spread strategy.

        Args:
            underlying_symbol: Underlying stock symbol
            signal_generator: Underlying signal generator
            max_risk_per_trade: Maximum risk per trade as fraction of portfolio
            preferred_short_dte: Preferred days to expiration for short leg
            preferred_long_dte: Preferred days to expiration for long leg
            preferred_moneyness: Preferred moneyness for options (ATM percentage)
            risk_free_rate: Risk-free rate for pricing models
            max_contracts_per_trade: Maximum number of contracts per trade
        """
        self.underlying_symbol = underlying_symbol
        self.signal_generator = signal_generator or SignalGenerator()
        self.max_risk_per_trade = max_risk_per_trade
        self.preferred_short_dte = preferred_short_dte
        self.preferred_long_dte = preferred_long_dte
        self.preferred_moneyness = preferred_moneyness
        self.risk_free_rate = risk_free_rate
        self.max_contracts_per_trade = max_contracts_per_trade
        self.pricing_model = OptionPricingModel(risk_free_rate)

        logger.info(f"Calendar spread strategy initialized for {underlying_symbol}")

    def generate_calendar_spread_signals(
        self,
        market_data: pd.DataFrame,
        option_chain: pd.DataFrame,
        current_date: Optional[datetime] = None
    ) -> List[Dict]:
        """Generate calendar spread signals based on volatility term structure.

        Args:
            market_data: DataFrame with underlying price and indicator data
            option_chain: DataFrame with current option chain data
            current_date: Current date (None for today)

        Returns:
            List of signal dictionaries
        """
        if current_date is None:
            current_date = datetime.now()

        signals = []

        # Get underlying signal to determine if we have volatility expectations
        underlying_signal = self.signal_generator.get_signal(market_data, current_date)

        # For calendar spreads, we often expect:
        # - Low near-term volatility (cheap short-term options)
        # - Higher expected longer-term volatility (expensive long-term options)
        # Or we expect an upcoming event that will increase near-term volatility

        # Get underlying price
        underlying_price = self._get_underlying_price(market_data, current_date)
        if underlying_price is None:
            return signals

        # Filter option chain for options with appropriate DTE
        options = option_chain[
            option_chain['expiration_date'].notna()
        ].copy()

        if options.empty:
            logger.warning("No options found in chain")
            return signals

        # Calculate days to expiration
        options['days_to_exp'] = options['expiration_date'].apply(
            lambda x: (datetime.strptime(x, '%Y-%m-%d') - current_date).days
        )

        # Separate calls and puts
        calls = options[options['option_type'] == 'call'].copy()
        puts = options[options['option_type'] == 'put'].copy()

        # Generate calendar spreads for both calls and puts
        for option_type, opt_df in [('call', calls), ('put', puts)]:
            if opt_df.empty:
                continue

            # Filter to preferred DTE ranges
            short_options = opt_df[
                opt_df['days_to_exp'].isin(self.preferred_short_dte) &
                (opt_df['days_to_exp'] > 0)
            ].copy()

            long_options = opt_df[
                opt_df['days_to_exp'].isin(self.preferred_long_dte) &
                (opt_df['days_to_exp'] > 0)
            ].copy()

            if short_options.empty or long_options.empty:
                logger.debug(f"No {option_type} options found in preferred DTE ranges")
                continue

            # Calculate moneyness for each option
            short_options['moneyness'] = (short_options['strike_price'] - underlying_price) / underlying_price
            long_options['moneyness'] = (long_options['strike_price'] - underlying_price) / underlying_price

            # Filter to preferred moneyness range (ATM options)
            min_moneyness, max_moneyness = self.preferred_moneyness
            short_options = short_options[
                (short_options['moneyness'] >= min_moneyness) &
                (short_options['moneyness'] <= max_moneyness)
            ]

            long_options = long_options[
                (long_options['moneyness'] >= min_moneyness) &
                (long_options['moneyness'] <= max_moneyness)
            ]

            if short_options.empty or long_options.empty:
                logger.debug(f"No {option_type} options found in preferred moneyness range")
                continue

            # For each combination of short and long expiration, check for calendar spread
            for short_dte in self.preferred_short_dte:
                short_expiry_options = short_options[short_options['days_to_exp'] == short_dte].copy()

                if short_expiry_options.empty:
                    continue

                for long_dte in self.preferred_long_dte:
                    if long_dte <= short_dte:  # Long expiration must be after short expiration
                        continue

                    long_expiry_options = long_options[long_options['days_to_exp'] == long_dte].copy()

                    if long_expiry_options.empty:
                        continue

                    # Try to find matching strikes
                    calendar_signal = self._find_calendar_spread(
                        short_expiry_options, long_expiry_options,
                        underlying_price, short_dte, long_dte, option_type, current_date
                    )

                    if calendar_signal is not None:
                        signals.append(calendar_signal)

        logger.info(f"Generated {len(signals)} calendar spread signals")
        return signals

    def _find_calendar_spread(
        self,
        short_options: pd.DataFrame,
        long_options: pd.DataFrame,
        underlying_price: float,
        short_dte: int,
        long_dte: int,
        option_type: str,
        current_date: datetime
    ) -> Optional[Dict]:
        """Find a suitable calendar spread from available options.

        Args:
            short_options: DataFrame of short-term options
            long_options: DataFrame of long-term options
            underlying_price: Current underlying price
            short_dte: Short-term days to expiration
            long_dte: Long-term days to expiration
            option_type: 'call' or 'put'
            current_date: Current date

        Returns:
            Signal dictionary or None if no suitable spread found
        """
        # Look for options with the same (or very close) strike price
        # We want to match strikes as closely as possible

        best_match = None
        min_strike_diff = float('inf')

        for _, short_opt in short_options.iterrows():
            short_strike = short_opt['strike_price']
            short_symbol = short_opt['option_symbol']

            # Find closest strike in long options
            long_options['strike_diff'] = abs(long_options['strike_price'] - short_strike)
            closest_long = long_options.loc[long_options['strike_diff'].idxmin()]

            strike_diff = closest_long['strike_diff']

            if strike_diff < min_strike_diff:
                min_strike_diff = strike_diff
                best_match = {
                    'short_strike': short_strike,
                    'short_symbol': short_symbol,
                    'short_expiry': short_opt['expiration_date'],
                    'long_strike': closest_long['strike_price'],
                    'long_symbol': closest_long['option_symbol'],
                    'long_expiry': closest_long['expiration_date'],
                    'strike_diff': strike_diff
                }

        if best_match is None or best_match['strike_diff'] > 0.5:  # Strike difference tolerance
            logger.debug(f"No suitable matching strikes found for {option_type} calendar spread")
            return None

        # Get mid prices for both options
        try:
            short_mid = self._get_option_mid_price_from_row(
                short_options,
                short_options[short_options['option_symbol'] == best_match['short_symbol']].iloc[0]
            )
            long_mid = self._get_option_mid_price_from_row(
                long_options,
                long_options[long_options['option_symbol'] == best_match['long_symbol']].iloc[0]
            )

            if short_mid is None or long_mid is None:
                logger.debug("Could not get mid prices for calendar spread legs")
                return None

            # For long calendar spread: we sell short-term option, buy long-term option
            # Net debit = long_mid - short_mid
            net_debit = long_mid - short_mid

            if net_debit <= 0:
                logger.debug(f"Invalid net debit for calendar spread: {net_debit}")
                return None

        except Exception as e:
            logger.debug(f"Error calculating calendar spread pricing: {e}")
            return None

        # Create signal
        signal = {
            'underlying_symbol': self.underlying_symbol,
            'signal_type': f'calendar_spread_{option_type}',
            'signal_strength': 0.7,  # Moderate confidence - term structure plays are nuanced
            'underlying_price': underlying_price,
            'strike_price': best_match['short_strike'],  # Use short strike as reference
            'short_expiration': best_match['short_expiry'],
            'long_expiration': best_match['long_expiry'],
            'short_dte': short_dte,
            'long_dte': long_dte,
            'option_type': option_type,
            'short_symbol': best_match['short_symbol'],
            'long_symbol': best_match['long_symbol'],
            'net_debit': net_debit,
            'timestamp': current_date
        }

        return signal

    def _get_option_mid_price_from_row(
        self,
        df: pd.DataFrame,
        row: pd.Series
    ) -> Optional[float]:
        """Get mid price from a dataframe row."""
        bid = row.get('bid_price')
        ask = row.get('ask_price')
        last = row.get('last_price')

        if bid is not None and ask is not None:
            return (bid + ask) / 2
        elif last is not None:
            return last
        else:
            return None

    def create_calendar_spread_position(
        self,
        signal: Dict,
        portfolio_value: float,
        current_date: Optional[datetime] = None
    ) -> Optional[CalendarSpreadPosition]:
        """Create a calendar spread position from a signal.

        Args:
            signal: Signal dictionary from generate_calendar_spread_signals
            portfolio_value: Current portfolio value
            current_date: Current date (None for today)

        Returns:
            CalendarSpreadPosition object or None
        """
        if current_date is None:
            current_date = datetime.now()

        # Extract signal details
        underlying_symbol = signal['underlying_symbol']
        underlying_price = signal['underlying_price']
        strike_price = signal['strike_price']
        short_expiration = signal['short_expiration']
        long_expiration = signal['long_expiration']
        option_type = signal['option_type']
        short_symbol = signal['short_symbol']
        long_symbol = signal['long_symbol']
        net_debit = signal['net_debit']

        # Calculate maximum risk allowed for this trade
        max_risk_dollars = portfolio_value * self.max_risk_per_trade

        # Risk per calendar spread = net debit
        risk_per_spread = net_debit * 100  # Per spread (1 contract each leg)

        if risk_per_spread <= 0:
            logger.error(f"Invalid risk per calendar spread: {risk_per_spread}")
            return None

        # Calculate maximum number of spreads we can trade
        max_spreads = int(max_risk_dollars / risk_per_spread)

        if max_spreads < 1:
            logger.warning(f"Not enough capital for even 1 calendar spread: need ${risk_per_spread:.2f}")
            return None

        # Use maximum contracts we can afford (respecting max_contracts_per_trade limit)
        quantity = min(max_spreads, self.max_contracts_per_trade)

        # Calculate actual risk
        actual_risk = quantity * risk_per_spread

        # Create position
        position = CalendarSpreadPosition(
            underlying_symbol=underlying_symbol,
            short_expiration=short_expiration,
            long_expiration=long_expiration,
            strike_price=strike_price,
            option_type=option_type,
            short_quantity=-quantity,  # Short near-term option
            long_quantity=quantity,    # Long longer-term option
            entry_date=current_date,
            entry_price=net_debit,     # Net debit paid
            max_profit=0,              # Will be calculated in __post_init__
            max_loss=0                 # Will be calculated in __post_init__
        )

        logger.info(
            f"Created {option_type} calendar spread: {quantity} spreads {underlying_symbol} "
            f"strike ${strike_price:.2f} "
            f"short: {short_symbol} exp {short_expiration} "
            f"long: {long_symbol} exp {long_expiration} "
            f"debit: ${net_debit:.2f} risk: ${actual_risk:.2f}"
        )

        return position

    def exit_calendar_spread(
        self,
        position: CalendarSpreadPosition,
        option_chain: pd.DataFrame,
        current_date: datetime
    ) -> Tuple[bool, float, str]:
        """Determine if a calendar spread should be exited.

        Args:
            position: Current calendar spread position
            option_chain: Current option chain data
            current_date: Current date

        Returns:
            Tuple of (should_exit, exit_value, reason)
        """
        # Check if short-term option has expired
        short_exp_date = datetime.strptime(position.short_expiration, '%Y-%m-%d')
        days_to_short_exp = (short_exp_date - current_date).days

        if days_to_short_exp <= 0:
            # Short-term option has expired - calculate settlement
            return self._calculate_calendar_spread_expiration(position, option_chain, current_date)

        # Get current mid prices for both legs
        short_mid = self._get_option_mid_price_from_chain(
            option_chain, position.strike_price, position.option_type, position.short_expiration
        )
        long_mid = self._get_option_mid_price_from_chain(
            option_chain, position.strike_price, position.option_type, position.long_expiration
        )

        if short_mid is None or long_mid is None:
            logger.warning(f"Could not get prices for calendar spread exit calculation")
            return False, 0.0, "Missing price data"

        # Calculate current calendar spread value
        # Long calendar spread: short near-term, long longer-term
        # Current value = (long_mid - short_mid) * 100 * quantity
        current_value = (long_mid - short_mid) * 100 * position.long_quantity

        # Original debit paid
        original_debit = position.entry_price * 100 * position.long_quantity

        # Current P&L (we want the spread to widen in our favor)
        current_pnl = current_value - original_debit

        # Exit conditions
        # 1. Take profit at 50% of max profit
        if current_pnl >= 0.5 * position.max_profit:
            return True, current_value, f"Take profit reached ({current_pnl:.2f})"

        # 2. Stop loss at 50% of max loss
        if current_pnl <= -0.5 * position.max_loss:
            return True, current_value, f"Stop loss triggered ({current_pnl:.2f})"

        # 3. Time decay - exit if too close to short-term expiration
        if days_to_short_exp <= 3:
            return True, current_value, f"Time decay exit ({days_to_short_exp} days to short exp)"

        # 4. If we've captured most of the expected profit early
        # Could add more sophisticated logic based on volatility changes

        return False, current_value, "Hold position"

    def _get_option_mid_price_from_chain(
        self,
        option_chain: pd.DataFrame,
        strike_price: float,
        option_type: str,
        expiration_date: str
    ) -> Optional[float]:
        """Get mid price for a specific option from option chain."""
        matching = option_chain[
            (abs(option_chain['strike_price'] - strike_price) < 0.25) &
            (option_chain['option_type'] == option_type) &
            (option_chain['expiration_date'] == expiration_date)
        ]

        if matching.empty:
            return None

        option = matching.iloc[0]
        bid = option.get('bid_price')
        ask = option.get('ask_price')
        last = option.get('last_price')

        if bid is not None and ask is not None:
            return (bid + ask) / 2
        elif last is not None:
            return last
        else:
            return None

    def _get_underlying_price(
        self,
        market_data: Optional[pd.DataFrame],
        current_date: datetime
    ) -> Optional[float]:
        """Get underlying price from market data."""
        if market_data is None or market_data.empty:
            return None

        # Get the most recent price
        try:
            return float(market_data.iloc[-1]['adjusted_close'])
        except (KeyError, IndexError, ValueError):
            logger.warning("Could not extract underlying price from market data")
            return None

    def _calculate_calendar_spread_expiration(
        self,
        position: CalendarSpreadPosition,
        option_chain: pd.DataFrame,
        current_date: datetime
    ) -> Tuple[bool, float, str]:
        """Calculate calendar spread value at short-term expiration.

        Args:
            position: Calendar spread position
            option_chain: Current option chain data (for underlying price)
            current_date: Current date (should be near short expiration)

        Returns:
            Tuple of (should_exit, expiration_value, reason)
        """
        # At short-term expiration, we need the underlying settlement price
        # Get it from the most recent market data
        underlying_settlement_price = self._get_underlying_price(option_chain, current_date)
        if underlying_settlement_price is None:
            # Fallback to using underlying price from signal if we can't get current data
            logger.warning("Could not get underlying settlement price, using 0 as placeholder")
            underlying_settlement_price = 0.0  # Better to use 0 than a random placeholder

        # Short-term option expires
        # Short-term option value at expiration:
        # For call: max(0, S - K)
        # For put: max(0, K - S)
        S = underlying_settlement_price
        K = position.strike_price

        if position.option_type == 'call':
            short_term_value = max(S - K, 0)
        else:  # put
            short_term_value = max(K - S, 0)

        # Remember we are SHORT the short-term option, so we lose this value
        short_term_value = -short_term_value

        # Long-term option still has time value
        # We need to estimate its value
        # Simplified: use Black-Scholes with reduced time to expiration
        long_days_remaining = (
            datetime.strptime(position.long_expiration, '%Y-%m-%d') - current_date
        ).days

        if long_days_remaining <= 0:
            # Long-term also expired
            long_term_value = 0
        else:
            # Approximate long-term value using intrinsic value + time value
            # This is a simplification - in practice we'd use option pricing
            time_to_exp_years = long_days_remaining / 365.0
            # Very rough approximation: long option still has 50% of its time value
            long_term_value = max(S - K, 0) if position.option_type == 'call' else max(K - S, 0)
            # Add some time value (this is highly approximate)
            long_term_value += 0.5 * (abs(position.entry_price) * 100) * (long_days_remaining / 360)

        # Remember we are LONG the long-term option
        # Total position value = short_term_value + long_term_value
        expiration_value = (short_term_value + long_term_value) * 100 * position.long_quantity

        # Original debit paid
        original_debit = position.entry_price * 100 * position.long_quantity

        # P&L at expiration
        pnl_at_expiration = expiration_value - original_debit

        logger.info(
            f"Calendar spread short-term expired. Underlying settlement: ${underlying_settlement_price:.2f}, "
            f"Position value: ${expiration_value:.2f}, Original debit: ${original_debit:.2f}, "
            f"P&L: ${pnl_at_expiration:.2f}"
        )

        return True, expiration_value, f"Short-term expired at {position.short_expiration}"


if __name__ == "__main__":
    # Example usage
    import pandas as pd
    from datetime import datetime, timedelta

    # Create sample option chain data
    sample_data = []
    base_date_short = datetime.now() + timedelta(days=14)
    base_date_long = datetime.now() + timedelta(days=45)
    exp_date_short = base_date_short.strftime('%Y-%m-%d')
    exp_date_long = base_date_long.strftime('%Y-%m-%d')

    # Generate sample options for calendar spread
    underlying_price = 150.0

    # ATM options around 150 strike
    for strike in [148, 150, 152]:
        # Short-term call option
        sample_data.append({
            'option_symbol': f'AAPL{base_date_short.strftime("%y%m%d")}C{int(strike*1000):08d}',
            'underlying_symbol': 'AAPL',
            'expiration_date': exp_date_short,
            'option_type': 'call',
            'strike_price': strike,
            'bid_price': max(0, underlying_price - strike + 3.0) * 0.8,
            'ask_price': max(0, underlying_price - strike + 3.0) * 0.9,
            'last_price': max(0, underlying_price - strike + 3.0) * 0.85,
            'volume': 100,
            'open_interest': 500
        })

        # Long-term call option
        sample_data.append({
            'option_symbol': f'AAPL{base_date_long.strftime("%y%m%d")}C{int(strike*1000):08d}',
            'underlying_symbol': 'AAPL',
            'expiration_date': exp_date_long,
            'option_type': 'call',
            'strike_price': strike,
            'bid_price': max(0, underlying_price - strike + 5.0) * 0.8,
            'ask_price': max(0, underlying_price - strike + 5.0) * 0.9,
            'last_price': max(0, underlying_price - strike + 5.0) * 0.85,
            'volume': 100,
            'open_interest': 500
        })

        # Short-term put option
        sample_data.append({
            'option_symbol': f'AAPL{base_date_short.strftime("%y%m%d")}P{int(strike*1000):08d}',
            'underlying_symbol': 'AAPL',
            'expiration_date': exp_date_short,
            'option_type': 'put',
            'strike_price': strike,
            'bid_price': max(0, strike - underlying_price + 3.0) * 0.8,
            'ask_price': max(0, strike - underlying_price + 3.0) * 0.9,
            'last_price': max(0, strike - underlying_price + 3.0) * 0.85,
            'volume': 100,
            'open_interest': 500
        })

        # Long-term put option
        sample_data.append({
            'option_symbol': f'AAPL{base_date_long.strftime("%y%m%d")}P{int(strike*1000):08d}',
            'underlying_symbol': 'AAPL',
            'expiration_date': exp_date_long,
            'option_type': 'put',
            'strike_price': strike,
            'bid_price': max(0, strike - underlying_price + 5.0) * 0.8,
            'ask_price': max(0, strike - underlying_price + 5.0) * 0.9,
            'last_price': max(0, strike - underlying_price + 5.0) * 0.85,
            'volume': 100,
            'open_interest': 500
        })

    option_chain = pd.DataFrame(sample_data)

    # Create sample market data
    market_data = pd.DataFrame({
        'date': [datetime.now() - timedelta(days=i) for i in range(5, 0, -1)],
        'adjusted_close': [149, 150, 151, 150, 149],
        'short_ma': [150.0] * 5,
        'medium_ma': [150.0] * 5,
        'composite_score': [0.1, 0.0, -0.1, 0.0, 0.1]  # Mixed signals
    })

    # Initialize strategy
    cs_strategy = CalendarSpreadStrategy('AAPL')

    # Generate signals
    signals = cs_strategy.generate_calendar_spread_signals(market_data, option_chain)

    print(f"Generated {len(signals)} calendar spread signals")

    # Create a position from first signal if available
    if signals:
        signal = signals[0]
        print(f"Signal: {signal}")

        # Create position
        position = cs_strategy.create_calendar_spread_position(signal, portfolio_value=100000)
        if position:
            print(f"Created position: {position}")

            # Check exit condition
            should_exit, exit_value, reason = cs_strategy.exit_calendar_spread(
                position, option_chain, datetime.now()
            )
            print(f"Exit recommendation: {should_exit} - {reason}")
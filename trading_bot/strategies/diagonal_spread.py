"""Diagonal spread strategy implementation."""

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
class DiagonalSpreadPosition:
    """Represents a diagonal spread position."""
    underlying_symbol: str
    short_expiration: str   # Near-term expiration
    long_expiration: str    # Longer-term expiration
    short_strike: float     # Strike for short-term option
    long_strike: float      # Strike for long-term option
    option_type: str        # 'call' or 'put'
    short_quantity: int     # Number of short-term contracts (negative for short)
    long_quantity: int      # Number of long-term contracts (positive for long)
    entry_date: datetime
    entry_price: float  # Net debit/credit (positive for debit spread, negative for credit)
    max_profit: float
    max_loss: float

    def __post_init__(self):
        """Calculate derived values after initialization."""
        # For diagonal spread, max profit/loss depends on structure
        # This is a simplified calculation - in practice would require more complex modeling

        if self.entry_price > 0:  # Debit spread (we paid to enter)
            # Max loss = net debit paid
            self.max_loss = abs(self.entry_price) * 100 * abs(self.long_quantity)
            # Max profit is approximate - depends on price movement and time decay
            self.max_profit = self.max_loss * 1.5  # Rough approximation
        else:  # Credit spread (we received credit to enter)
            # Max profit = net credit received
            self.max_profit = abs(self.entry_price) * 100 * abs(self.long_quantity)
            # Max loss is approximate - depends on price movement
            self.max_loss = self.max_profit * 1.5  # Rough approximation


class DiagonalSpreadStrategy:
    """Diagonal spread strategy for volatility and directional plays."""

    def __init__(
        self,
        underlying_symbol: str,
        signal_generator: Optional[SignalGenerator] = None,
        max_risk_per_trade: float = 0.02,  # 2% of portfolio per trade
        preferred_short_dte: List[int] = [7, 14, 21],   # Short-term: 1-3 weeks
        preferred_long_dte: List[int] = [30, 45, 60],   # Long-term: 1-2 months
        strike_spread_range: Tuple[float, float] = (0.02, 0.10),  # 2% to 10% strike difference
        risk_free_rate: float = 0.05,
        max_contracts_per_trade: int = 10  # Maximum number of contracts per trade
    ):
        """Initialize diagonal spread strategy.

        Args:
            underlying_symbol: Underlying stock symbol
            signal_generator: Underlying signal generator
            max_risk_per_trade: Maximum risk per trade as fraction of portfolio
            preferred_short_dte: Preferred days to expiration for short leg
            preferred_long_dte: Preferred days to expiration for long leg
            strike_spread_range: Preferred range for strike price difference (as fraction of underlying)
            risk_free_rate: Risk-free rate for pricing models
            max_contracts_per_trade: Maximum number of contracts per trade
        """
        self.underlying_symbol = underlying_symbol
        self.signal_generator = signal_generator or SignalGenerator()
        self.max_risk_per_trade = max_risk_per_trade
        self.preferred_short_dte = preferred_short_dte
        self.preferred_long_dte = preferred_long_dte
        self.strike_spread_range = strike_spread_range
        self.risk_free_rate = risk_free_rate
        self.max_contracts_per_trade = max_contracts_per_trade
        self.pricing_model = OptionPricingModel(risk_free_rate)

        logger.info(f"Diagonal spread strategy initialized for {underlying_symbol}")

    def generate_diagonal_spread_signals(
        self,
        market_data: pd.DataFrame,
        option_chain: pd.DataFrame,
        current_date: Optional[datetime] = None,
        is_bullish: bool = True
    ) -> List[Dict]:
        """Generate diagonal spread signals based on market conditions.

        Args:
            market_data: DataFrame with underlying price and indicator data
            option_chain: DataFrame with current option chain data
            current_date: Current date (None for today)
            is_bullish: If True, generate bullish diagonal spreads; if False, bearish

        Returns:
            List of signal dictionaries
        """
        if current_date is None:
            current_date = datetime.now()

        signals = []

        # Get underlying signal to determine market direction and strength
        underlying_signal = self.signal_generator.get_signal(market_data, current_date)

        # For diagonal spreads, we want alignment between our bias and market signals
        # Bullish diagonal: buy long-term call, sell short-term call at higher strike
        # Bearish diagonal: buy long-term put, sell short-term put at lower strike

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

        # Choose option type based on desired bias
        opt_df = calls if is_bullish else puts
        option_type = 'call' if is_bullish else 'put'

        if opt_df.empty:
            logger.warning(f"No {option_type} options found")
            return signals

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
            return signals

        # For each combination of short and long expiration, look for diagonal spreads
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

                # Try to find suitable diagonal spread
                diagonal_signal = self._find_diagonal_spread(
                    short_expiry_options, long_expiry_options,
                    underlying_price, short_dte, long_dte, option_type, is_bullish, current_date
                )

                if diagonal_signal is not None:
                    signals.append(diagonal_signal)

        logger.info(f"Generated {len(signals)} diagonal spread signals")
        return signals

    def _find_diagonal_spread(
        self,
        short_options: pd.DataFrame,
        long_options: pd.DataFrame,
        underlying_price: float,
        short_dte: int,
        long_dte: int,
        option_type: str,
        is_bullish: bool,
        current_date: datetime
    ) -> Optional[Dict]:
        """Find a suitable diagonal spread from available options.

        Args:
            short_options: DataFrame of short-term options
            long_options: DataFrame of long-term options
            underlying_price: Current underlying price
            short_dte: Short-term days to expiration
            long_dte: Long-term days to expiration
            option_type: 'call' or 'put'
            is_bullish: True for bullish spread, False for bearish
            current_date: Current date

        Returns:
            Signal dictionary or None if no suitable spread found
        """
        min_strike_diff = float('inf')
        best_match = None

        # For bullish diagonal spread with calls:
        # Buy longer-term call at lower strike, sell shorter-term call at higher strike
        # For bearish diagonal spread with puts:
        # Buy longer-term put at higher strike, sell shorter-term put at lower strike

        if is_bullish and option_type == 'call':
            # Bullish call diagonal: long LEAP call at lower strike, short near-term call at higher strike
            for _, long_opt in long_options.iterrows():
                long_strike = long_opt['strike_price']
                long_symbol = long_opt['option_symbol']

                # Look for short-term calls with higher strike
                higher_strike_options = short_options[
                    short_options['strike_price'] > long_strike
                ].copy()

                if higher_strike_options.empty:
                    continue

                # Find the closest higher strike (to minimize strike spread)
                higher_strike_options['strike_diff'] = higher_strike_options['strike_price'] - long_strike
                closest_higher = higher_strike_options.loc[higher_strike_options['strike_diff'].idxmin()]

                strike_diff = closest_higher['strike_diff']
                strike_diff_pct = strike_diff / underlying_price

                # Check if strike difference is within preferred range
                min_pct, max_pct = self.strike_spread_range
                if min_pct <= strike_diff_pct <= max_pct:
                    if strike_diff < min_strike_diff:
                        min_strike_diff = strike_diff
                        best_match = {
                            'long_strike': long_strike,
                            'long_symbol': long_symbol,
                            'long_expiry': long_opt['expiration_date'],
                            'short_strike': closest_higher['strike_price'],
                            'short_symbol': closest_higher['option_symbol'],
                            'short_expiry': closest_higher['expiration_date'],
                            'strike_diff': strike_diff,
                            'strike_diff_pct': strike_diff_pct
                        }

        elif not is_bullish and option_type == 'put':
            # Bearish put diagonal: long LEAP put at higher strike, short near-term put at lower strike
            for _, long_opt in long_options.iterrows():
                long_strike = long_opt['strike_price']
                long_symbol = long_opt['option_symbol']

                # Look for short-term puts with lower strike
                lower_strike_options = short_options[
                    short_options['strike_price'] < long_strike
                ].copy()

                if lower_strike_options.empty:
                    continue

                # Find the closest lower strike (to minimize strike spread)
                lower_strike_options['strike_diff'] = long_strike - lower_strike_options['strike_price']
                closest_lower = lower_strike_options.loc[lower_strike_options['strike_diff'].idxmin()]

                strike_diff = closest_lower['strike_diff']
                strike_diff_pct = strike_diff / underlying_price

                # Check if strike difference is within preferred range
                min_pct, max_pct = self.strike_spread_range
                if min_pct <= strike_diff_pct <= max_pct:
                    if strike_diff < min_strike_diff:
                        min_strike_diff = strike_diff
                        best_match = {
                            'long_strike': long_strike,
                            'long_symbol': long_symbol,
                            'long_expiry': long_opt['expiration_date'],
                            'short_strike': closest_lower['strike_price'],
                            'short_symbol': closest_lower['option_symbol'],
                            'short_expiry': closest_lower['expiration_date'],
                            'strike_diff': strike_diff,
                            'strike_diff_pct': strike_diff_pct
                        }

        if best_match is None:
            logger.debug(f"No suitable diagonal spread found for {option_type} {'bullish' if is_bullish else 'bearish'}")
            return None

        # Get mid prices for both options
        try:
            long_mid = self._get_option_mid_price_from_row(
                long_options,
                long_options[long_options['option_symbol'] == best_match['long_symbol']].iloc[0]
            )
            short_mid = self._get_option_mid_price_from_row(
                short_options,
                short_options[short_options['option_symbol'] == best_match['short_symbol']].iloc[0]
            )

            if long_mid is None or short_mid is None:
                logger.debug("Could not get mid prices for diagonal spread legs")
                return None

            # For diagonal spread:
            # Bullish call: Buy long-term call, Sell short-term call
            # Bearish put: Buy long-term put, Sell short-term put
            # Net debit = long_mid - short_mid (typically debit spread)
            net_price = long_mid - short_mid

        except Exception as e:
            logger.debug(f"Error calculating diagonal spread pricing: {e}")
            return None

        # Create signal
        signal = {
            'underlying_symbol': self.underlying_symbol,
            'signal_type': f'diagonal_spread_{option_type}_{"bullish" if is_bullish else "bearish"}',
            'signal_strength': 0.75,  # Good confidence for directional volatility plays
            'underlying_price': underlying_price,
            'long_expiration': best_match['long_expiry'],
            'short_expiration': best_match['short_expiry'],
            'long_dte': long_dte,
            'short_dte': short_dte,
            'option_type': option_type,
            'long_strike': best_match['long_strike'],
            'short_strike': best_match['short_strike'],
            'long_symbol': best_match['long_symbol'],
            'short_symbol': best_match['short_symbol'],
            'strike_difference': best_match['strike_diff'],
            'strike_difference_pct': best_match['strike_diff_pct'],
            'net_price': net_price,  # Net debit if positive, net credit if negative
            'is_bullish': is_bullish,
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

    def create_diagonal_spread_position(
        self,
        signal: Dict,
        portfolio_value: float,
        current_date: Optional[datetime] = None
    ) -> Optional[DiagonalSpreadPosition]:
        """Create a diagonal spread position from a signal.

        Args:
            signal: Signal dictionary from generate_diagonal_spread_signals
            portfolio_value: Current portfolio value
            current_date: Current date (None for today)

        Returns:
            DiagonalSpreadPosition object or None
        """
        if current_date is None:
            current_date = datetime.now()

        # Extract signal details
        underlying_symbol = signal['underlying_symbol']
        underlying_price = signal['underlying_price']
        long_expiration = signal['long_expiration']
        short_expiration = signal['short_expiration']
        long_strike = signal['long_strike']
        short_strike = signal['short_strike']
        option_type = signal['option_type']
        long_symbol = signal['long_symbol']
        short_symbol = signal['short_symbol']
        net_price = signal['net_price']
        is_bullish = signal['is_bullish']

        # Calculate maximum risk allowed for this trade
        max_risk_dollars = portfolio_value * self.max_risk_per_trade

        # Risk per diagonal spread = |net_price| * 100 (debit if positive, credit risk if negative)
        # For debit spreads (net_price > 0): risk = net_price * 100
        # For credit spreads (net_price < 0): risk is more complex, use approximate
        if net_price > 0:  # Debit spread
            risk_per_spread = net_price * 100
        else:  # Credit spread - approximate risk
            risk_per_spread = abs(net_price) * 100 * 1.5  # Approximate

        if risk_per_spread <= 0:
            logger.error(f"Invalid risk per diagonal spread: {risk_per_spread}")
            return None

        # Calculate maximum number of spreads we can trade
        max_spreads = int(max_risk_dollars / risk_per_spread)

        if max_spreads < 1:
            logger.warning(f"Not enough capital for even 1 diagonal spread: need ${risk_per_spread:.2f}")
            return None

        # Use maximum contracts we can afford (respecting max_contracts_per_trade limit)
        quantity = min(max_spreads, self.max_contracts_per_trade)

        # Calculate actual risk
        actual_risk = quantity * risk_per_spread

        # Create position
        # For diagonal spread:
        # Bullish call: long LEAP call (+), short near-term call (-)
        # Bearish put: long LEAP put (+), short near-term put (-)
        long_quantity = quantity
        short_quantity = -quantity  # Short position

        position = DiagonalSpreadPosition(
            underlying_symbol=underlying_symbol,
            short_expiration=short_expiration,
            long_expiration=long_expiration,
            short_strike=short_strike,
            long_strike=long_strike,
            option_type=option_type,
            short_quantity=short_quantity,
            long_quantity=long_quantity,
            entry_date=current_date,
            entry_price=net_price,
            max_profit=0,  # Will be calculated in __post_init__
            max_loss=0     # Will be calculated in __post_init__
        )

        logger.info(
            f"Created {'bullish' if is_bullish else 'bearish'} {option_type} diagonal spread: "
            f"{quantity} spreads {underlying_symbol} "
            f"LONG: {long_symbol} {long_expiration} K{long_strike:.2f} "
            f"SHORT: {short_symbol} {short_expiration} K{short_strike:.2f} "
            f"Net: ${net_price:.2f} ({'debit' if net_price > 0 else 'credit'}) risk: ${actual_risk:.2f}"
        )

        return position

    def exit_diagonal_spread(
        self,
        position: DiagonalSpreadPosition,
        option_chain: pd.DataFrame,
        current_date: datetime
    ) -> Tuple[bool, float, str]:
        """Determine if a diagonal spread should be exited.

        Args:
            position: Current diagonal spread position
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
            return self._calculate_diagonal_spread_expiration(position, option_chain, current_date)

        # Get current mid prices for both legs
        long_mid = self._get_option_mid_price_from_chain(
            option_chain, position.long_strike, position.option_type, position.long_expiration
        )
        short_mid = self._get_option_mid_price_from_chain(
            option_chain, position.short_strike, position.option_type, position.short_expiration
        )

        if long_mid is None or short_mid is None:
            logger.warning(f"Could not get prices for diagonal spread exit calculation")
            return False, 0.0, "Missing price data"

        # Calculate current diagonal spread value
        # Long diagonal: long LEAP option (+), short near-term option (-)
        # Current value = (long_mid - short_mid) * 100 * quantity
        current_value = (long_mid - short_mid) * 100 * position.long_quantity

        # Original price paid/received
        original_value = position.entry_price * 100 * position.long_quantity

        # Current P&L
        # For debit spreads (entry_price > 0): profit when current_value > original_value
        # For credit spreads (entry_price < 0): profit when current_value < original_value (we want to buy back cheaper)
        current_pnl = current_value - original_value

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

        # 4. For bullish spreads, exit if underlying drops significantly below long strike
        # 5. For bearish spreads, exit if underlying rises significantly above long strike
        underlying_price = self._get_underlying_price(None, current_date)  # Would need market data
        if underlying_price is not None:
            if position.option_type == 'call' and underlying_price < position.long_strike * 0.8:
                return True, current_value, f"Underlying dropped below long call strike ({underlying_price:.2f})"
            elif position.option_type == 'put' and underlying_price > position.long_strike * 1.2:
                return True, current_value, f"Underlying rose above long put strike ({underlying_price:.2f})"

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

    def _calculate_diagonal_spread_expiration(
        self,
        position: DiagonalSpreadPosition,
        option_chain: pd.DataFrame,
        current_date: datetime
    ) -> Tuple[bool, float, str]:
        """Calculate diagonal spread value at short-term expiration.

        Args:
            position: Diagonal spread position
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
        K = position.short_strike

        if position.option_type == 'call':
            short_term_value = max(S - K, 0)
        else:  # put
            short_term_value = max(K - S, 0)

        # Remember we are SHORT the short-term option, so we lose/gain this value
        short_term_value = -short_term_value

        # Long-term option still has time value
        # We need to estimate its value
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
            # Very rough approximation: long option still has intrinsic + some time value
            intrinsic_value = max(S - position.long_strike, 0) if position.option_type == 'call' else max(position.long_strike - S, 0)
            # Add some time value (highly approximate)
            long_term_value = intrinsic_value + (0.3 * abs(position.entry_price) * 100) * (long_days_remaining / 360)

        # Remember we are LONG the long-term option
        # Total position value = long_term_value + short_term_value
        expiration_value = (long_term_value + short_term_value) * 100 * position.long_quantity

        # Original price paid/received
        original_value = position.entry_price * 100 * position.long_quantity

        # P&L at expiration
        pnl_at_expiration = expiration_value - original_value

        logger.info(
            f"Diagonal spread short-term expired. Underlying settlement: ${underlying_settlement_price:.2f}, "
            f"Position value: ${expiration_value:.2f}, Original value: ${original_value:.2f}, "
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

    # Generate sample options for diagonal spread
    underlying_price = 150.0

    # For bullish diagonal call: long LEAP call at lower strike, short near-term call at higher strike
    long_strike = 145  # Lower strike for long LEAP call
    short_strike = 155  # Higher strike for short-term call

    # Long-term call (LEAP)
    sample_data.append({
        'option_symbol': f'AAPL{base_date_long.strftime("%y%m%d")}C{int(long_strike*1000):08d}',
        'underlying_symbol': 'AAPL',
        'expiration_date': exp_date_long,
        'option_type': 'call',
        'strike_price': long_strike,
        'bid_price': max(0, underlying_price - long_strike + 8.0) * 0.8,
        'ask_price': max(0, underlying_price - long_strike + 8.0) * 0.9,
        'last_price': max(0, underlying_price - long_strike + 8.0) * 0.85,
        'volume': 50,
        'open_interest': 200
    })

    # Short-term call
    sample_data.append({
        'option_symbol': f'AAPL{base_date_short.strftime("%y%m%d")}C{int(short_strike*1000):08d}',
        'underlying_symbol': 'AAPL',
        'expiration_date': exp_date_short,
        'option_type': 'call',
        'strike_price': short_strike,
        'bid_price': max(0, underlying_price - short_strike + 3.0) * 0.8,
        'ask_price': max(0, underlying_price - short_strike + 3.0) * 0.9,
        'last_price': max(0, underlying_price - short_strike + 3.0) * 0.85,
        'volume': 100,
        'open_interest': 500
    })

    # For bearish diagonal put: long LEAP put at higher strike, short near-term put at lower strike
    long_put_strike = 155  # Higher strike for long LEAP put
    short_put_strike = 145  # Lower strike for short-term put

    # Long-term put (LEAP)
    sample_data.append({
        'option_symbol': f'AAPL{base_date_long.strftime("%y%m%d")}P{int(long_put_strike*1000):08d}',
        'underlying_symbol': 'AAPL',
        'expiration_date': exp_date_long,
        'option_type': 'put',
        'strike_price': long_put_strike,
        'bid_price': max(0, long_put_strike - underlying_price + 8.0) * 0.8,
        'ask_price': max(0, long_put_strike - underlying_price + 8.0) * 0.9,
        'last_price': max(0, long_put_strike - underlying_price + 8.0) * 0.85,
        'volume': 50,
        'open_interest': 200
    })

    # Short-term put
    sample_data.append({
        'option_symbol': f'AAPL{base_date_short.strftime("%y%m%d")}P{int(short_put_strike*1000):08d}',
        'underlying_symbol': 'AAPL',
        'expiration_date': exp_date_short,
        'option_type': 'put',
        'strike_price': short_put_strike,
        'bid_price': max(0, short_put_strike - underlying_price + 3.0) * 0.8,
        'ask_price': max(0, short_put_strike - underlying_price + 3.0) * 0.9,
        'last_price': max(0, short_put_strike - underlying_price + 3.0) * 0.85,
        'volume': 100,
        'open_interest': 500
    })

    option_chain = pd.DataFrame(sample_data)

    # Create sample market data showing bullish trend
    market_data = pd.DataFrame({
        'date': [datetime.now() - timedelta(days=i) for i in range(5, 0, -1)],
        'adjusted_close': [148, 149, 150, 151, 152],  # Rising trend
        'short_ma': [150.0] * 5,
        'medium_ma': [150.0] * 5,
        'composite_score': [0.3, 0.4, 0.5, 0.4, 0.3]  # Bullish signals
    })

    # Initialize strategy
    diag_strategy = DiagonalSpreadStrategy('AAPL')

    # Generate bullish diagonal spread signals
    print("Generating bullish diagonal spread signals...")
    bullish_signals = diag_strategy.generate_diagonal_spread_signals(market_data, option_chain, is_bullish=True)
    print(f"Generated {len(bullish_signals)} bullish diagonal spread signals")

    # Generate bearish diagonal spread signals
    print("Generating bearish diagonal spread signals...")
    bearish_signals = diag_strategy.generate_diagonal_spread_signals(market_data, option_chain, is_bullish=False)
    print(f"Generated {len(bearish_signals)} bearish diagonal spread signals")

    # Create a position from first bullish signal if available
    if bullish_signals:
        signal = bullish_signals[0]
        print(f"Bullish signal: {signal}")

        # Create position
        position = diag_strategy.create_diagonal_spread_position(signal, portfolio_value=100000)
        if position:
            print(f"Created position: {position}")

            # Check exit condition
            should_exit, exit_value, reason = diag_strategy.exit_diagonal_spread(
                position, option_chain, datetime.now()
            )
            print(f"Exit recommendation: {should_exit} - {reason}")
"""Iron condor strategy implementation."""

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
class IronCondorPosition:
    """Represents an iron condor position."""
    underlying_symbol: str
    expiration_date: str
    put_long_strike: float   # Lower strike put (long)
    put_short_strike: float  # Higher strike put (short)
    call_short_strike: float # Lower strike call (short)
    call_long_strike: float  # Higher strike call (long)
    put_long_quantity: int   # Number of put long contracts
    put_short_quantity: int  # Number of put short contracts
    call_short_quantity: int # Number of call short contracts
    call_long_quantity: int  # Number of call long contracts
    entry_date: datetime
    entry_price: float  # Net credit received (positive for iron condor)
    max_profit: float
    max_loss: float
    breakeven_lower: float
    breakeven_upper: float

    def __post_init__(self):
        """Calculate derived values after initialization."""
        # For iron condor:
        # Buy put at K1, sell put at K2, sell call at K3, buy call at K4
        # Where K1 < K2 < K3 < K4

        # Max profit = net credit received
        self.max_profit = self.entry_price * 100 * abs(self.put_long_quantity)

        # Max loss = width of either spread minus net credit
        # Typically both spreads have same width
        put_width = abs(self.put_short_strike - self.put_long_strike)
        call_width = abs(self.call_long_strike - self.call_short_strike)
        width = min(put_width, call_width)  # Use the narrower spread
        self.max_loss = (width * 100 * abs(self.put_long_quantity)) - self.max_profit

        # Breakeven points
        # Lower breakeven = put_long_strike + net credit received
        # Upper breakeven = call_short_strike - net credit received
        credit_per_share = self.entry_price * 100
        self.breakeven_lower = self.put_long_strike + credit_per_share
        self.breakeven_upper = self.call_short_strike - credit_per_share


class IronCondorStrategy:
    """Iron condor strategy for range-bound markets."""

    def __init__(
        self,
        underlying_symbol: str,
        signal_generator: Optional[SignalGenerator] = None,
        max_risk_per_trade: float = 0.02,  # 2% of portfolio per trade
        preferred_dte: List[int] = [30, 45, 60],
        put_wing_width: float = 5.0,   # Width of put spread in dollars
        call_wing_width: float = 5.0,  # Width of call spread in dollars
        body_width: float = 10.0,      # Width between short put and short call
        risk_free_rate: float = 0.05,
        max_contracts_per_trade: int = 10  # Maximum number of contracts per trade
    ):
        """Initialize iron condor strategy.

        Args:
            underlying_symbol: Underlying stock symbol
            signal_generator: Underlying signal generator (for regime detection)
            max_risk_per_trade: Maximum risk per trade as fraction of portfolio
            preferred_dte: Preferred days to expiration
            put_wing_width: Width of put wing (distance between long and short put)
            call_wing_width: Width of call wing (distance between long and short call)
            body_width: Width of body (distance between short put and short call)
            risk_free_rate: Risk-free rate for pricing models
            max_contracts_per_trade: Maximum number of contracts per trade
        """
        self.underlying_symbol = underlying_symbol
        self.signal_generator = signal_generator or SignalGenerator()
        self.max_risk_per_trade = max_risk_per_trade
        self.preferred_dte = preferred_dte
        self.put_wing_width = put_wing_width
        self.call_wing_width = call_wing_width
        self.body_width = body_width
        self.risk_free_rate = risk_free_rate
        self.max_contracts_per_trade = max_contracts_per_trade
        self.pricing_model = OptionPricingModel(risk_free_rate)

        logger.info(f"Iron condor strategy initialized for {underlying_symbol}")

    def generate_iron_condor_signals(
        self,
        market_data: pd.DataFrame,
        option_chain: pd.DataFrame,
        current_date: Optional[datetime] = None
    ) -> List[Dict]:
        """Generate iron condor signals based on range-bound market conditions.

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

        # Get underlying signal to determine if market is range-bound
        underlying_signal = self.signal_generator.get_signal(market_data, current_date)

        # For iron condor, we want low volatility, neutral markets
        # We'll look for signals indicating low trend/momentum
        if underlying_signal is None:
            logger.debug("No underlying signal available")
            return signals

        # Check if conditions are suitable for iron condor
        # We want: low trend strength, low volatility, range-bound
        signal_strength = underlying_signal.signal_strength
        signal_type = underlying_signal.signal_type

        # Prefer neutral or weak signals
        if signal_type not in ['neutral', 'weak_bullish', 'weak_bearish']:
            # If we have a strong directional signal, iron condor is not suitable
            if signal_strength > 0.5:  # Only avoid if signal is strong
                logger.debug(f"Signal too strong for iron condor: {signal_type} strength {signal_strength}")
                return signals

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

        # Filter to preferred DTE and future expirations
        options = options[
            options['days_to_exp'].isin(self.preferred_dte) &
            (options['days_to_exp'] > 0)
        ]

        if options.empty:
            logger.debug(f"No options found in preferred DTE range: {self.preferred_dte}")
            return signals

        # Separate calls and puts
        calls = options[options['option_type'] == 'call'].copy()
        puts = options[options['option_type'] == 'put'].copy()

        if calls.empty or puts.empty:
            logger.warning("Missing either calls or puts in filtered chain")
            return signals

        # For each preferred DTE, try to construct iron condor
        for dte in self.preferred_dte:
            dte_calls = calls[calls['days_to_exp'] == dte].copy()
            dte_puts = puts[puts['days_to_exp'] == dte].copy()

            if dte_calls.empty or dte_puts.empty:
                continue

            # Try to find suitable strikes for iron condor
            iron_condor_signal = self._construct_iron_condor(
                dte_calls, dte_puts, underlying_price, dte, current_date
            )

            if iron_condor_signal is not None:
                signals.append(iron_condor_signal)

        logger.info(f"Generated {len(signals)} iron condor signals")
        return signals

    def _construct_iron_condor(
        self,
        calls: pd.DataFrame,
        puts: pd.DataFrame,
        underlying_price: float,
        dte: int,
        current_date: datetime
    ) -> Optional[Dict]:
        """Attempt to construct an iron condor from available options.

        Args:
            calls: DataFrame of call options for specific DTE
            puts: DataFrame of put options for specific DTE
            underlying_price: Current underlying price
            dte: Days to expiration
            current_date: Current date

        Returns:
            Signal dictionary or None if cannot construct
        """
        # We want:
        # Put wing: long put at K1, short put at K2 (K1 < K2)
        # Call wing: short call at K3, long call at K4 (K3 < K4)
        # Body: K2 to K3 (distance between short put and short call)
        # Wings: K1 to K2 and K3 to K4

        target_body_center = underlying_price  # Ideally center the body on underlying price

        # Look for put spread (wing) below the money
        # Look for call spread (wing) above the money

        # Sort puts by strike (ascending)
        puts_sorted = puts.sort_values('strike_price')
        calls_sorted = calls.sort_values('strike_price')

        # Find put wing: look for two puts with correct wing width
        put_wing = None
        for i in range(len(puts_sorted) - 1):
            strike_long = puts_sorted.iloc[i]['strike_price']      # Lower strike (long put)
            strike_short = puts_sorted.iloc[i + 1]['strike_price'] # Higher strike (short put)

            wing_width = strike_short - strike_long
            if abs(wing_width - self.put_wing_width) < 0.5:  # Allow 0.5 tolerance
                # Check if both are OTM or ATM
                if strike_short <= underlying_price:  # Both strikes <= underlying (OTM/ATM puts)
                    put_wing = {
                        'long_strike': strike_long,
                        'short_strike': strike_short,
                        'long_symbol': puts_sorted.iloc[i]['option_symbol'],
                        'short_symbol': puts_sorted.iloc[i + 1]['option_symbol']
                    }
                    break

        # Find call wing: look for two calls with correct wing width
        call_wing = None
        for i in range(len(calls_sorted) - 1):
            strike_short = calls_sorted.iloc[i]['strike_price']      # Lower strike (short call)
            strike_long = calls_sorted.iloc[i + 1]['strike_price']   # Higher strike (long call)

            wing_width = strike_long - strike_short
            if abs(wing_width - self.call_wing_width) < 0.5:  # Allow 0.5 tolerance
                # Check if both are OTM or ATM
                if strike_long >= underlying_price:  # Both strikes >= underlying (OTM/ATM calls)
                    call_wing = {
                        'short_strike': strike_short,
                        'long_strike': strike_long,
                        'short_symbol': calls_sorted.iloc[i]['option_symbol'],
                        'long_symbol': calls_sorted.iloc[i + 1]['option_symbol']
                    }
                    break

        if put_wing is None or call_wing is None:
            logger.debug(f"Could not find suitable wings for iron condor at DTE {dte}")
            return None

        # Check body width (distance between short put and short call)
        body_width_actual = call_wing['short_strike'] - put_wing['short_strike']
        if abs(body_width_actual - self.body_width) > 2.0:  # Allow 2.0 tolerance
            logger.debug(f"Body width mismatch: {body_width_actual:.2f} vs target {self.body_width}")
            return None

        # Calculate approximate entry price (net credit)
        # We need mid prices for all four legs
        try:
            put_long_mid = self._get_option_mid_price_from_df(
                puts, put_wing['long_strike'], 'put', dte
            )
            put_short_mid = self._get_option_mid_price_from_df(
                puts, put_wing['short_strike'], 'put', dte
            )
            call_short_mid = self._get_option_mid_price_from_df(
                calls, call_wing['short_strike'], 'call', dte
            )
            call_long_mid = self._get_option_mid_price_from_df(
                calls, call_wing['long_strike'], 'call', dte
            )

            if None in [put_long_mid, put_short_mid, call_short_mid, call_long_mid]:
                logger.debug("Could not get mid prices for all legs")
                return None

            # Iron condor: BUY put_long, SELL put_short, SELL call_short, BUY call_long
            # Net credit = (put_short_mid + call_short_mid) - (put_long_mid + call_long_mid)
            net_credit = (put_short_mid + call_short_mid) - (put_long_mid + call_long_mid)

            if net_credit <= 0:
                logger.debug(f"Invalid net credit for iron condor: {net_credit}")
                return None

        except Exception as e:
            logger.debug(f"Error calculating iron condor pricing: {e}")
            return None

        # Create signal
        signal = {
            'underlying_symbol': self.underlying_symbol,
            'signal_type': 'iron_condor',
            'signal_strength': max(0.1, 1.0 - underlying_signal.signal_strength),  # Invert strength for neutral preference
            'underlying_price': underlying_price,
            'expiration_date': (current_date + timedelta(days=dte)).strftime('%Y-%m-%d'),
            'dte': dte,
            'put_long_strike': put_wing['long_strike'],
            'put_short_strike': put_wing['short_strike'],
            'call_short_strike': call_wing['short_strike'],
            'call_long_strike': call_wing['long_strike'],
            'put_long_symbol': put_wing['long_symbol'],
            'put_short_symbol': put_wing['short_symbol'],
            'call_short_symbol': call_wing['short_symbol'],
            'call_long_symbol': call_wing['long_symbol'],
            'net_credit': net_credit,
            'timestamp': current_date
        }

        return signal

    def _get_option_mid_price_from_df(
        self,
        df: pd.DataFrame,
        strike_price: float,
        option_type: str,
        dte: int
    ) -> Optional[float]:
        """Get mid price for a specific option from dataframe."""
        # Filter for options matching strike, type, and DTE
        # We need to match expiration date as well, but we don't have it easily
        # For now, just match strike and type - in practice would need to match expiration too
        matching = df[
            (df['strike_price'] == strike_price) &
            (df['option_type'] == option_type)
        ]

        if matching.empty:
            # Try approximate match
            matching = df[
                (abs(df['strike_price'] - strike_price) < 0.25) &
                (df['option_type'] == option_type)
            ]

        if matching.empty:
            return None

        # Use first match
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

    def create_iron_condor_position(
        self,
        signal: Dict,
        portfolio_value: float,
        current_date: Optional[datetime] = None
    ) -> Optional[IronCondorPosition]:
        """Create an iron condor position from a signal.

        Args:
            signal: Signal dictionary from generate_iron_condor_signals
            portfolio_value: Current portfolio value
            current_date: Current date (None for today)

        Returns:
            IronCondorPosition object or None
        """
        if current_date is None:
            current_date = datetime.now()

        # Extract signal details
        underlying_symbol = signal['underlying_symbol']
        underlying_price = signal['underlying_price']
        expiration_date = signal['expiration_date']
        put_long_strike = signal['put_long_strike']
        put_short_strike = signal['put_short_strike']
        call_short_strike = signal['call_short_strike']
        call_long_strike = signal['call_long_strike']
        net_credit = signal['net_credit']

        # Calculate maximum risk allowed for this trade
        max_risk_dollars = portfolio_value * self.max_risk_per_trade

        # Calculate width of the spreads (should be equal for standard iron condor)
        put_width = abs(put_short_strike - put_long_strike)
        call_width = abs(call_long_strike - call_short_strike)
        width = min(put_width, call_width)  # Use the narrower wing

        # Risk per iron condor = width * 100 - net credit
        risk_per_condor = (width * 100) - (net_credit * 100)

        if risk_per_condor <= 0:
            logger.error(f"Invalid risk per iron condor: {risk_per_condor}")
            return None

        # Calculate maximum number of condors we can trade
        max_conductors = int(max_risk_dollars / risk_per_condor)

        if max_conductors < 1:
            logger.warning(f"Not enough capital for even 1 iron condor: need ${risk_per_condor:.2f}")
            return None

        # Use maximum contracts we can afford (respecting max_contracts_per_trade limit)
        quantity = min(max_conductors, self.max_contracts_per_trade)

        # Calculate actual risk
        actual_risk = quantity * risk_per_condor

        # Create position
        position = IronCondorPosition(
            underlying_symbol=underlying_symbol,
            expiration_date=expiration_date,
            put_long_strike=put_long_strike,
            put_short_strike=put_short_strike,
            call_short_strike=call_short_strike,
            call_long_strike=call_long_strike,
            put_long_quantity=quantity,
            put_short_quantity=-quantity,  # Short
            call_short_quantity=-quantity, # Short
            call_long_quantity=quantity,
            entry_date=current_date,
            entry_price=net_credit,
            max_profit=0,  # Will be calculated in __post_init__
            max_loss=0,    # Will be calculated in __post_init__
            breakeven_lower=0,  # Will be calculated in __post_init__
            breakeven_upper=0   # Will be calculated in __post_init__
        )

        logger.info(
            f"Created iron condor: {quantity} lots {underlying_symbol} "
            f"[{put_long_strike}/{put_short_strike}] [{call_short_strike}/{call_long_strike}] "
            f"exp {expiration_date} credit: ${net_credit:.2f} risk: ${actual_risk:.2f}"
        )

        return position

    def exit_iron_condor(
        self,
        position: IronCondorPosition,
        option_chain: pd.DataFrame,
        current_date: datetime
    ) -> Tuple[bool, float, str]:
        """Determine if an iron condor should be exited.

        Args:
            position: Current iron condor position
            option_chain: Current option chain data
            current_date: Current date

        Returns:
            Tuple of (should_exit, exit_value, reason)
        """
        # Check if expired
        exp_date = datetime.strptime(position.expiration_date, '%Y-%m-%d')
        days_to_exp = (exp_date - current_date).days

        if days_to_exp <= 0:
            # Option has expired - calculate settlement
            return self._calculate_iron_condor_expiration(position, option_chain, exp_date)

        # Get current mid prices for all four legs
        put_long_mid = self._get_option_mid_price_from_chain(
            option_chain, position.put_long_strike, 'put', position.expiration_date
        )
        put_short_mid = self._get_option_mid_price_from_chain(
            option_chain, position.put_short_strike, 'put', position.expiration_date
        )
        call_short_mid = self._get_option_mid_price_from_chain(
            option_chain, position.call_short_strike, 'call', position.expiration_date
        )
        call_long_mid = self._get_option_mid_price_from_chain(
            option_chain, position.call_long_strike, 'call', position.expiration_date
        )

        if None in [put_long_mid, put_short_mid, call_short_mid, call_long_mid]:
            logger.warning(f"Could not get prices for iron condor exit calculation")
            return False, 0.0, "Missing price data"

        # Calculate current iron condor value
        # Iron condor: +put_long -put_short -call_short +call_long
        # Current value = (put_long_mid - put_short_mid - call_short_mid + call_long_mid) * 100 * quantity
        current_value = (
            put_long_mid - put_short_mid - call_short_mid + call_long_mid
        ) * 100 * position.put_long_quantity

        # Original credit received
        original_credit = position.entry_price * 100 * position.put_long_quantity

        # Current P&L (we want to buy back for less than we sold for)
        current_pnl = original_credit - current_value

        # Exit conditions
        # 1. Take profit at 50% of max profit
        if current_pnl >= 0.5 * position.max_profit:
            return True, current_value, f"Take profit reached ({current_pnl:.2f})"

        # 2. Stop loss at 50% of max loss
        if current_pnl <= -0.5 * position.max_loss:
            return True, current_value, f"Stop loss triggered ({current_pnl:.2f})"

        # 3. Time decay - exit if too close to expiration
        if days_to_exp <= 7:
            return True, current_value, f"Time decay exit ({days_to_exp} days to exp)"

        # 4. Underlying price breached wings (outside our profit range)
        underlying_price = self._get_underlying_price(None, current_date)  # Would need market data
        if underlying_price is not None:
            if underlying_price <= position.breakeven_lower or underlying_price >= position.breakeven_upper:
                return True, current_value, f"Underlying outside breakevens ({underlying_price:.2f})"

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

    def _calculate_iron_condor_expiration(
        self,
        position: IronCondorPosition,
        option_chain: pd.DataFrame,
        expiration_date: datetime
    ) -> Tuple[bool, float, str]:
        """Calculate iron condor value at expiration.

        Args:
            position: Iron condor position
            option_chain: Current option chain data (for underlying price)
            expiration_date: Expiration date

        Returns:
            Tuple of (should_exit, expiration_value, reason)
        """
        # At expiration, we need the underlying settlement price
        # Get it from the most recent market data
        underlying_settlement_price = self._get_underlying_price(None, expiration_date)
        if underlying_settlement_price is None:
            # Fallback to using underlying price from signal if we can't get current data
            logger.warning("Could not get underlying settlement price, using underlying price from signal")
            underlying_settlement_price = 150.0  # This should come from the signal in practice

        # Calculate value of each leg at expiration
        # Put long: max(0, put_long_strike - S)
        # Put short: max(0, put_short_strike - S) * -1 (we are short)
        # Call short: max(0, S - call_short_strike) * -1 (we are short)
        # Call long: max(0, S - call_long_strike)

        S = underlying_settlement_price

        put_long_value = max(position.put_long_strike - S, 0)
        put_short_value = -max(position.put_short_strike - S, 0)
        call_short_value = -max(S - position.call_short_strike, 0)
        call_long_value = max(S - position.call_long_strike, 0)

        # Total value per spread
        value_per_spread = put_long_value + put_short_value + call_short_value + call_long_value

        # Total position value
        expiration_value = value_per_spread * 100 * position.put_long_quantity

        # Original credit received
        original_credit = position.entry_price * 100 * position.put_long_quantity

        # P&L at expiration
        pnl_at_expiration = original_credit - expiration_value  # We want to buy back cheaper than we sold

        logger.info(
            f"Iron condor expired. Underlying settlement: ${underlying_settlement_price:.2f}, "
            f"Position value: ${expiration_value:.2f}, Original credit: ${original_credit:.2f}, "
            f"P&L: ${pnl_at_expiration:.2f}"
        )

        return True, expiration_value, f"Expired at {expiration_date.strftime('%Y-%m-%d')}"


if __name__ == "__main__":
    # Example usage
    import pandas as pd
    from datetime import datetime, timedelta

    # Create sample option chain data
    sample_data = []
    base_date = datetime.now() + timedelta(days=45)
    exp_date = base_date.strftime('%Y-%m-%d')

    # Generate sample options for iron condor
    underlying_price = 150.0

    # Put wing: long put at 140, short put at 145
    # Call wing: short call at 155, long call at 160
    strikes = [140, 145, 155, 160]

    for strike in strikes:
        # Put option
        sample_data.append({
            'option_symbol': f'AAPL{base_date.strftime("%y%m%d")}P{int(strike*1000):08d}',
            'underlying_symbol': 'AAPL',
            'expiration_date': exp_date,
            'option_type': 'put',
            'strike_price': strike,
            'bid_price': max(0, strike - underlying_price + 2.0) * 0.8,
            'ask_price': max(0, strike - underlying_price + 2.0) * 0.9,
            'last_price': max(0, strike - underlying_price + 2.0) * 0.85,
            'volume': 50,
            'open_interest': 200
        })

        # Call option
        sample_data.append({
            'option_symbol': f'AAPL{base_date.strftime("%y%m%d")}C{int(strike*1000):08d}',
            'underlying_symbol': 'AAPL',
            'expiration_date': exp_date,
            'option_type': 'call',
            'strike_price': strike,
            'bid_price': max(0, underlying_price - strike + 2.0) * 0.8,
            'ask_price': max(0, underlying_price - strike + 2.0) * 0.9,
            'last_price': max(0, underlying_price - strike + 2.0) * 0.85,
            'volume': 50,
            'open_interest': 200
        })

    option_chain = pd.DataFrame(sample_data)

    # Create sample market data showing neutral/low volatility conditions
    market_data = pd.DataFrame({
        'date': [datetime.now() - timedelta(days=i) for i in range(10, 0, -1)],
        'adjusted_close': [150, 150.2, 149.8, 150.1, 150.0, 149.9, 150.2, 150.1, 150.0, 149.9],
        'short_ma': [150.0] * 10,
        'medium_ma': [150.0] * 10,
        'composite_score': [0.0, 0.1, -0.1, 0.0, 0.0, -0.1, 0.1, 0.0, 0.0, -0.1]  # Neutral scores
    })

    # Initialize strategy
    ic_strategy = IronCondorStrategy('AAPL')

    # Generate signals
    signals = ic_strategy.generate_iron_condor_signals(market_data, option_chain)

    print(f"Generated {len(signals)} iron condor signals")

    # Create a position from first signal if available
    if signals:
        signal = signals[0]
        print(f"Signal: {signal}")

        # Create position
        position = ic_strategy.create_iron_condor_position(signal, portfolio_value=100000)
        if position:
            print(f"Created position: {position}")

            # Check exit condition
            should_exit, exit_value, reason = ic_strategy.exit_iron_condor(
                position, option_chain, datetime.now()
            )
            print(f"Exit recommendation: {should_exit} - {reason}")
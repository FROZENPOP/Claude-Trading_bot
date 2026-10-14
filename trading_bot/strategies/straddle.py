"""Straddle strategy implementation for long and short straddles."""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from trading_bot.strategies.option_pricing import OptionPricingModel, parse_option_symbol
from trading_bot.strategies.signals import SignalGenerator
from trading_bot.risk_management import RiskManager, RiskMetrics

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
    max_loss: float     # Maximum loss for the position
    max_profit: float   # Maximum profit for the position
    breakeven_upper: float  # Upper breakeven price
    breakeven_lower: float  # Lower breakeven price
    is_long: bool       # True for long straddle (buy call + buy put), False for short straddle (sell call + sell put)


@dataclass
class StraddleSignal:
    """Represents a signal to enter a straddle."""
    underlying_symbol: str
    signal_type: str  # 'long_straddle' or 'short_straddle'
    signal_strength: float  # 0-1 scale
    recommended_dte: List[int]  # Preferred days to expiration
    recommended_iv_rank: Tuple[float, float]  # Preferred IV rank range
    spread_width_preference: str  # Not used for straddles but kept for consistency
    timestamp: datetime
    # Additional fields populated during signal generation
    underlying_price: Optional[float] = None
    call_symbol: Optional[str] = None
    put_symbol: Optional[str] = None
    call_bid: Optional[float] = None
    call_ask: Optional[float] = None
    put_bid: Optional[float] = None
    put_ask: Optional[float] = None
    days_to_exp: Optional[int] = None


class StraddleStrategy:
    """Straddle strategy for options trading."""

    def __init__(
        self,
        underlying_symbol: str,
        signal_generator: Optional[SignalGenerator] = None,
        max_risk_per_trade: float = 0.02,  # 2% of portfolio per trade
        preferred_dte: List[int] = [21, 30, 45, 60],
        max_contracts_per_trade: int = 10,  # Maximum number of straddles per trade
        risk_free_rate: float = 0.05,
        use_greeks_for_filtering: bool = True  # Whether to use Greeks for strike selection
    ):
        """Initialize straddle strategy.

        Args:
            underlying_symbol: The underlying stock symbol (e.g., 'AAPL')
            signal_generator: Underlying signal generator (if None, creates default)
            max_risk_per_trade: Maximum risk per trade as fraction of portfolio
            preferred_dte: Preferred days to expiration for options
            max_contracts_per_trade: Maximum number of contracts per trade
            risk_free_rate: Risk-free rate for pricing models
            use_greeks_for_filtering: Whether to use Greeks for filtering strikes
        """
        self.underlying_symbol = underlying_symbol
        self.signal_generator = signal_generator or SignalGenerator()
        self.max_risk_per_trade = max_risk_per_trade
        self.preferred_dte = preferred_dte
        self.max_contracts_per_trade = max_contracts_per_trade
        self.risk_free_rate = risk_free_rate
        self.use_greeks_for_filtering = use_greeks_for_filtering
        self.pricing_model = OptionPricingModel(risk_free_rate)
        self.risk_manager = RiskManager(risk_free_rate, max_risk_per_trade)

        logger.info(f"Straddle strategy initialized for {underlying_symbol}")

    def generate_straddle_signals(
        self,
        stock_data: pd.DataFrame,
        option_chain_data: pd.DataFrame,
        current_date: datetime,
        is_long: bool = True
    ) -> List[StraddleSignal]:
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

        # Convert current_date to date object if needed
        if isinstance(current_date, datetime):
            current_date_obj = current_date.date()
        elif hasattr(current_date, 'date'):
            current_date_obj = current_date.date()
        else:
            current_date_obj = current_date

        # Get underlying signal
        underlying_signal = self.signal_generator.get_signal(stock_data, current_date_obj)
        if underlying_signal is None:
            logger.debug("No underlying signal available")
            return signals

        # For straddles, we typically want high volatility expectations
        # Long straddles work well when expecting big moves (high IV expected)
        # Short straddles work well when expecting low volatility (IV expected to decrease)
        # We'll use signal strength as a proxy for conviction

        # Get underlying price
        underlying_price = self._get_underlying_price(stock_data, current_date_obj)
        if underlying_price is None:
            logger.warning("Could not get underlying price")
            return signals

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

        # Calculate days to expiration
        exp_options['days_to_exp'] = exp_options['expiration_date'].apply(
            lambda x: (datetime.strptime(x, '%Y-%m-%d').date() - current_date_obj).days
        )

        # Filter to preferred DTE and future expirations
        exp_options = exp_options[
            exp_options['days_to_exp'].isin(self.preferred_dte) &
            (exp_options['days_to_exp'] > 0)
        ]

        if exp_options.empty:
            logger.debug(f"No options found in preferred DTE range: {self.preferred_dte}")
            return signals

        # Get underlying price for moneyness calculation
        # Find ATM (at-the-money) strike - closest to current stock price
        if 'strike_price' in exp_options.columns:
            exp_options['strike_distance'] = abs(exp_options['strike_price'] - underlying_price)
            atm_options = exp_options.nsmallest(5, 'strike_distance')  # Get 5 closest strikes

            if atm_options.empty:
                logger.warning("Could not find ATM strikes")
                return signals

            atm_strike = atm_options.iloc[0]['strike_price']

            # Get call and put options near ATM strike
            # We'll look at strikes within a reasonable range around ATM
            lower_bound = atm_strike * 0.9  # 10% below ATM
            upper_bound = atm_strike * 1.1  # 10% above ATM

            nearby_options = exp_options[
                (exp_options['strike_price'] >= lower_bound) &
                (exp_options['strike_price'] <= upper_bound)
            ].copy()

            if nearby_options.empty:
                logger.warning("No options found near ATM strike")
                return signals

            # Group by strike price to find matching call/put pairs
            strikes = sorted(nearby_options['strike_price'].unique())

            for strike in strikes:
                call_options = nearby_options[
                    (nearby_options['strike_price'] == strike) &
                    (nearby_options['option_type'] == 'call')
                ]

                put_options = nearby_options[
                    (nearby_options['strike_price'] == strike) &
                    (nearby_options['option_type'] == 'put')
                ]

                if not call_options.empty and not put_options.empty:
                    call_option = call_options.iloc[0]
                    put_option = put_options.iloc[0]

                    # Calculate straddle cost (for long straddle) or credit (for short straddle)
                    call_price = self._get_option_mid_price(call_option)
                    put_price = self._get_option_mid_price(put_option)

                    if call_price is None or put_price is None:
                        # Try using last price if mid price not available
                        call_price = call_option.get('last_price')
                        put_price = put_option.get('last_price')

                    if call_price is None or put_price is None or call_price <= 0 or put_price <= 0:
                        logger.debug(f"Invalid prices for strike {strike}: call={call_price}, put={put_price}")
                        continue

                    straddle_price = call_price + put_price

                    # Calculate Greeks for risk assessment (if enabled)
                    greeks_info = None
                    if self.use_greeks_for_filtering:
                        time_to_expiry = exp_options.iloc[0]['days_to_exp'] / 365.0
                        try:
                            call_greeks = self.pricing_model.calculate_greeks(
                                underlying_price, strike, time_to_expiry,
                                self.risk_free_rate,
                                self._get_implied_volatility_from_option(call_option, underlying_price, strike, time_to_expiry),
                                'call'
                            )
                            put_greeks = self.pricing_model.calculate_greeks(
                                underlying_price, strike, time_to_expiry,
                                self.risk_free_rate,
                                self._get_implied_volatility_from_option(put_option, underlying_price, strike, time_to_expiry),
                                'put'
                            )
                            greeks_info = {
                                'call_delta': call_greeks['delta'],
                                'call_gamma': call_greeks['gamma'],
                                'call_theta': call_greeks['theta'],
                                'call_vega': call_greeks['vega'],
                                'put_delta': put_greeks['delta'],
                                'put_gamma': put_greeks['gamma'],
                                'put_theta': put_greeks['theta'],
                                'put_vega': put_greeks['vega'],
                                'time_to_expiry': time_to_expiry
                            }
                        except Exception as e:
                            logger.debug(f"Could not calculate Greeks for strike {strike}: {e}")

                    # Calculate position size based on risk limits
                    contract_multiplier = 100  # Standard option contract multiplier
                    straddle_cost = straddle_price * contract_multiplier  # Cost of 1 straddle contract

                    # Calculate how many straddles we can trade based on risk limit
                    max_dollar_risk = None  # Will be calculated in create_straddle_position

                    # Calculate breakeven points
                    breakeven_upper = strike + straddle_price
                    breakeven_lower = strike - straddle_price

                    # For long straddle: max loss is the premium paid, max profit is unlimited (theoretically)
                    # For short straddle: max profit is the premium received, max loss is unlimited (theoretically)
                    if is_long:
                        max_loss_per_contract = straddle_price * contract_multiplier
                        max_profit_per_contract = float('inf')  # Unlimited upside
                    else:
                        max_loss_per_contract = float('inf')  # Unlimited downside
                        max_profit_per_contract = straddle_price * contract_multiplier

                    signal = StraddleSignal(
                        underlying_symbol=self.underlying_symbol,
                        signal_type='long_straddle' if is_long else 'short_straddle',
                        signal_strength=underlying_signal.signal_strength,
                        recommended_dte=[int(exp_options.iloc[0]['days_to_exp'])],
                        recommended_iv_rank=(0.0, 1.0),  # Would need IV rank data for proper filtering
                        spread_width_preference="ATM",  # Straddles use ATM strikes
                        timestamp=current_date,
                        underlying_price=underlying_price,
                        call_symbol=call_option.get('symbol', ''),
                        put_symbol=put_option.get('symbol', ''),
                        call_bid=call_option.get('bid_price'),
                        call_ask=call_option.get('ask_price'),
                        put_bid=put_option.get('bid_price'),
                        put_ask=put_option.get('ask_price'),
                        days_to_exp=int(exp_options.iloc[0]['days_to_exp'])
                    )
                    # Store additional info in signal for later use
                    signal.__dict__.update({
                        'strike_price': strike,
                        'call_price': call_price,
                        'put_price': put_price,
                        'straddle_price': straddle_price,
                        'breakeven_upper': breakeven_upper,
                        'breakeven_lower': breakeven_lower,
                        'max_loss_per_contract': max_loss_per_contract,
                        'max_profit_per_contract': max_profit_per_contract,
                        'greeks_info': greeks_info
                    })

                    signals.append(signal)
                    logger.info(f"Generated {'long' if is_long else 'short'} straddle signal: "
                              f"{self.underlying_symbol} {strike} straddle expiring {target_expiration}")

        return signals

    def _get_underlying_price(
        self,
        stock_data: pd.DataFrame,
        current_date: datetime
    ) -> Optional[float]:
        """Get current underlying price from stock data."""
        if stock_data is not None and not stock_data.empty:
            # Get the most recent price
            if 'adjusted_close' in stock_data.columns:
                return float(stock_data['adjusted_close'].iloc[-1])
            elif 'close' in stock_data.columns:
                return float(stock_data['close'].iloc[-1])

        logger.warning("Unable to get underlying price from stock data")
        return None

    def _get_option_mid_price(self, option: pd.Series) -> Optional[float]:
        """Get mid price for an option."""
        bid = option.get('bid_price')
        ask = option.get('ask_price')

        if bid is not None and ask is not None:
            return (bid + ask) / 2
        elif option.get('last_price') is not None:
            return option['last_price']
        else:
            return None

    def _get_implied_volatility_from_option(
        self,
        option: pd.Series,
        underlying_price: float,
        strike_price: float,
        time_to_expiry: float
    ) -> Optional[float]:
        """Extract implied volatility from option price."""
        # This is a simplified approach - in practice we'd need to solve for IV
        # For now, we'll return a placeholder or try to get it from the option data
        iv = option.get('implied_volatility')
        if iv is not None:
            return float(iv)

        # If we don't have IV, we can't calculate it without an pricing model reversal
        # Return a reasonable default for now
        return 0.25  # 25% volatility as placeholder

    def create_straddle_position(
        self,
        signal: StraddleSignal,
        portfolio_value: float,
        current_date: Optional[datetime] = None
    ) -> Optional[Straddle]:
        """Create a straddle position from a signal using centralized risk management.

        Args:
            signal: StraddleSignal containing trade details
            portfolio_value: Current portfolio value for position sizing
            current_date: Current date (None for today)

        Returns:
            Straddle object or None if cannot create
        """
        if current_date is None:
            current_date = datetime.now()

        # Extract signal details
        underlying_symbol = signal.underlying_symbol
        strike_price = getattr(signal, 'strike_price', None)
        call_price = getattr(signal, 'call_price', None)
        put_price = getattr(signal, 'put_price', None)
        straddle_price = getattr(signal, 'straddle_price', None)
        days_to_exp = getattr(signal, 'days_to_exp', None)
        underlying_price = getattr(signal, 'underlying_price', None)

        if None in [strike_price, call_price, put_price, straddle_price, days_to_exp, underlying_price]:
            logger.error("Missing required signal information to create straddle")
            return None

        # Use RiskManager for position sizing
        # For straddles, the risk per unit is the straddle price (debit for long, credit for short)
        risk_per_unit = straddle_price * 100  # Per straddle (100 shares per contract)

        if risk_per_unit <= 0:
            logger.error(f"Invalid risk per unit: {risk_per_unit}")
            return None

        # Calculate position size using RiskManager
        position_sizing = self.risk_manager.calculate_position_size(
            portfolio_value=portfolio_value,
            risk_per_unit=risk_per_unit
        )

        if position_sizing.quantity < 1:
            logger.warning(f"Calculated quantity is less than 1: {position_sizing.quantity}")
            return None

        # Respect max contracts per trade limit
        quantity = min(position_sizing.quantity, self.max_contracts_per_trade)
        if quantity < 1:
            quantity = 1  # At least 1 contract

        # Calculate actual risk
        actual_risk = quantity * risk_per_unit

        # For long straddle: max loss is the premium paid, max profit is unlimited (theoretically)
        # For short straddle: max profit is the premium received, max loss is unlimited (theoretically)
        if signal.signal_type == 'long_straddle':
            max_loss = actual_risk
            max_profit = float('inf')  # Theoretically unlimited for long straddle
            call_quantity = quantity  # Positive for long
            put_quantity = quantity   # Positive for long
        else:  # short_straddle
            max_loss = float('inf')  # Theoretically unlimited for short straddle
            max_profit = actual_risk  # Maximum profit is the credit received
            call_quantity = -quantity  # Negative because we're short
            put_quantity = -quantity   # Negative because we're short

        # Create the straddle
        expiration_date = (current_date + timedelta(days=days_to_exp)).strftime('%Y-%m-%d')

        straddle = Straddle(
            underlying_symbol=underlying_symbol,
            expiration_date=expiration_date,
            strike_price=strike_price,
            call_quantity=call_quantity,
            put_quantity=put_quantity,
            entry_date=current_date,
            entry_price=straddle_price,
            max_loss=max_loss,
            max_profit=max_profit,
            breakeven_upper=getattr(signal, 'breakeven_upper', 0.0),
            breakeven_lower=getattr(signal, 'breakeven_lower', 0.0),
            is_long=(signal.signal_type == 'long_straddle')
        )

        logger.info(
            f"Created {signal.signal_type}: "
            f"{abs(call_quantity)} calls and {abs(put_quantity)} puts {underlying_symbol} "
            f"{strike_price} straddle expiring {expiration_date} "
            f"price: ${straddle_price:.2f} "
            f"{'debit' if signal.signal_type == 'long_straddle' else 'credit'}: ${actual_risk:.2f} "
            f"position size based on {self.max_risk_per_trade*100:.1f}% risk per trade"
        )

        return straddle

    def exit_straddle(
        self,
        straddle: Straddle,
        option_chain: pd.DataFrame,
        current_date: datetime
    ) -> Tuple[bool, float, str]:
        """Determine if a straddle should be exited and calculate exit value.

        Args:
            straddle: Current straddle position
            option_chain: Current option chain data
            current_date: Current date

        Returns:
            Tuple of (should_exit, exit_price, reason)
        """
        # Check if expired
        exp_date = datetime.strptime(straddle.expiration_date, '%Y-%m-%d')
        days_to_exp = (exp_date - current_date).days

        if days_to_exp <= 0:
            # Option has expired - calculate settlement value
            return self._calculate_expiration_settlement(straddle, option_chain, exp_date)

        # Get current mid prices for the straddle legs
        call_mid = self._get_current_straddle_leg_price(
            option_chain,
            straddle.underlying_symbol,
            straddle.expiration_date,
            straddle.strike_price,
            'call'
        )

        put_mid = self._get_current_straddle_leg_price(
            option_chain,
            straddle.underlying_symbol,
            straddle.expiration_date,
            straddle.strike_price,
            'put'
        )

        if call_mid is None or put_mid is None:
            logger.warning(f"Could not get prices for straddle exit calculation")
            return False, 0.0, "Missing price data"

        # Calculate current straddle value
        current_value = (call_mid + put_mid) * 100  # Value per straddle (100 shares per contract)

        # Calculate current P&L
        entry_cost = straddle.entry_price * 100  # Cost per straddle (debit for long, credit for short)
        if straddle.is_long:
            # Long straddle: P&L = current value - entry cost
            current_pnl = (current_value * abs(straddle.call_quantity)) - (entry_cost * abs(straddle.call_quantity))
        else:
            # Short straddle: P&L = entry cost - current value (we received credit, now we pay to close)
            current_pnl = (entry_cost * abs(straddle.call_quantity)) - (current_value * abs(straddle.call_quantity))

        # Standardized exit conditions (matching other strategies):
        # 1. Time decay - exit if <=7 days to expiration
        time_to_expiry = days_to_exp / 365.0
        is_safe, reason_msg = self.risk_manager.check_expiration_risk(
            time_to_expiry=time_to_expiry,
            max_days_to_expiry=7
        )
        if is_safe:
            return True, current_value, f"Time decay exit: {reason_msg}"

        # 2. Take profit at 50% of max profit
        # 3. Stop loss at 50% of max loss
        # For straddles, we define:
        # - Long straddle: max_loss = premium paid, max_profit = 2x premium paid (100% return target)
        # - Short straddle: max_profit = credit received, max_loss = 2x credit received (100% loss limit)

        if straddle.is_long:
            # Long straddle calculations
            max_loss = entry_cost * abs(straddle.call_quantity)  # Premium paid (max loss)
            max_profit_target = max_loss * 0.5  # 50% profit target (50% of debit at risk)
            stop_loss_level = -max_loss * 0.5  # 50% stop loss (50% of debit at risk)

            if current_pnl >= max_profit_target:
                return True, current_value, f"Take profit target reached (50% of debit at risk: ${current_pnl:.2f})"

            if current_pnl <= stop_loss_level:
                return True, current_value, f"Stop loss triggered (50% of debit at risk: ${current_pnl:.2f})"
        else:
            # Short straddle calculations
            max_profit = entry_cost * abs(straddle.call_quantity)  # Credit received (max profit)
            max_profit_target = max_profit * 0.5  # 50% profit target (50% of credit at risk)
            stop_loss_level = -max_profit * 0.5  # 50% stop loss (50% of credit at risk)

            if current_pnl >= max_profit_target:
                return True, current_value, f"Take profit target reached (50% of credit at risk: ${current_pnl:.2f})"

            if current_pnl <= stop_loss_level:
                return True, current_value, f"Stop loss triggered (50% of credit at risk: ${current_pnl:.2f})"

        return False, current_value, "Hold position"

    def _get_current_straddle_leg_price(
        self,
        option_chain: pd.DataFrame,
        underlying_symbol: str,
        expiration_date: str,
        strike_price: float,
        option_type: str
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
        straddle: Straddle,
        option_chain: pd.DataFrame,
        expiration_date: datetime
    ) -> Tuple[bool, float, str]:
        """Calculate settlement value at expiration.

        Args:
            straddle: Straddle position
            option_chain: Current option chain data (for underlying price)
            expiration_date: Expiration date

        Returns:
            Tuple of (should_exit, settlement_value, reason)
        """
        # At expiration, we need the underlying settlement price
        # Get it from market data if available
        underlying_settlement_price = self._get_underlying_price_from_chain(option_chain, expiration_date)
        if underlying_settlement_price is None:
            # Fallback - try to get from recent market data in option chain
            logger.warning("Could not get underlying settlement price from option chain")
            underlying_settlement_price = 0.0  # Better to use 0 than a random placeholder

        if straddle.is_long:
            # Long straddle settlement
            # Long call: max(0, S - K)
            # Long put: max(0, K - S)
            call_value = max(underlying_settlement_price - straddle.strike_price, 0)
            put_value = max(straddle.strike_price - underlying_settlement_price, 0)
            straddle_value = (call_value + put_value) * 100 * abs(straddle.call_quantity)
        else:
            # Short straddle settlement (we are short both call and put)
            # Short call: -max(0, S - K)
            # Short put: -max(0, K - S)
            call_value = -max(underlying_settlement_price - straddle.strike_price, 0)
            put_value = -max(straddle.strike_price - underlying_settlement_price, 0)
            straddle_value = (call_value + put_value) * 100 * abs(straddle.call_quantity)

        entry_cost = straddle.entry_price * 100 * abs(straddle.call_quantity)
        pnl_at_expiration = straddle_value - entry_cost

        logger.info(
            f"Straddle expired. Underlying settlement: ${underlying_settlement_price:.2f}, "
            f"Straddle value: ${straddle_value:.2f}, Entry cost: ${entry_cost:.2f}, "
            f"P&L: ${pnl_at_expiration:.2f}"
        )

        return True, straddle_value, f"Expired at {expiration_date.strftime('%Y-%m-%d')}"

    def _get_underlying_price_from_chain(
        self,
        option_chain: pd.DataFrame,
        expiration_date: datetime
    ) -> Optional[float]:
        """Try to get underlying price from option chain data."""
        # Look for any option to get underlying symbol, then we'd need external data
        # This is a limitation - we really need market data for underlying price
        # For now, return None to indicate we need external market data
        return None


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

    # Create sample stock data
    stock_data = pd.DataFrame({
        'date': [datetime.now() - timedelta(days=i) for i in range(5, 0, -1)],
        'adjusted_close': [148, 149, 150, 151, 152],
        'volume': [1000000] * 5
    })

    # Initialize strategy
    strategy = StraddleStrategy('AAPL')

    # Generate signals
    long_signals = strategy.generate_straddle_signals(stock_data, option_chain, datetime.now(), is_long=True)
    short_signals = strategy.generate_straddle_signals(stock_data, option_chain, datetime.now(), is_long=False)

    logger.info(f"Generated {len(long_signals)} long straddle signals")
    logger.info(f"Generated {len(short_signals)} short straddle signals")

    # Create a position from first signal if available
    if long_signals:
        signal = long_signals[0]
        logger.info(f"Signal: {signal.signal_type} with strength {signal.signal_strength}")

        # Create position
        position = strategy.create_straddle_position(signal, portfolio_value=100000)
        if position:
            logger.info(f"Created position: {position}")

            # Check exit condition
            should_exit, exit_price, reason = strategy.exit_straddle(
                position, option_chain, datetime.now()
            )
            logger.info(f"Exit recommendation: {should_exit} - {reason}")
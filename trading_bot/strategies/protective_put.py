"""Protective put strategy implementation."""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from trading_bot.strategies.option_pricing import OptionPricingModel, parse_option_symbol
from trading_bot.strategies.signals import SignalGenerator
from trading_bot.risk_management import RiskManager

logger = logging.getLogger(__name__)


@dataclass
class ProtectivePutPosition:
    """Represents a protective put position."""
    underlying_symbol: str
    underlying_quantity: int  # Number of shares owned
    put_symbol: str
    put_strike: float
    put_expiration: str
    put_quantity: int  # Number of put contracts purchased (positive)
    entry_date: datetime
    stock_entry_price: float  # Average price paid for stock
    put_entry_price: float  # Price paid for buying put
    max_profit: float  # Theoretically unlimited
    max_loss: float    # Limited to (stock_price - put_strike) + put_premium
    breakeven: float   # Stock price where total P&L = 0

    def __post_init__(self):
        """Calculate derived values after initialization."""
        # For protective put, max loss is limited
        # Max loss occurs when stock goes to zero:
        # Loss = stock_value - put_value_at_zero - put_premium_paid
        # But put value at zero = put_strike * 100 * quantity (put is ITM)
        # Actually, max loss = (stock_entry_price - put_strike) * shares + put_premium_paid
        put_cost = self.put_entry_price * 100 * self.put_quantity
        stock_value = self.underlying_quantity * self.stock_entry_price
        self.max_loss = ((self.stock_entry_price - self.put_strike) * self.underlying_quantity) + put_cost

        # Breakeven: stock price where gains from stock appreciation equal put premium paid
        # (stock_price - stock_entry_price) * shares = put_premium_paid
        # stock_price = stock_entry_price + (put_premium_paid / shares)
        if self.underlying_quantity != 0:
            put_cost_per_share = (self.put_entry_price * 100 * self.put_quantity) / self.underlying_quantity
            self.breakeven = self.stock_entry_price + put_cost_per_share
        else:
            self.breakeven = 0


class ProtectivePutStrategy:
    """Protective put strategy: long stock + long put."""

    def __init__(
        self,
        underlying_symbol: str,
        signal_generator: Optional[SignalGenerator] = None,
        max_position_size: float = 0.10,  # 10% of portfolio per trade
        preferred_dte: List[int] = [21, 30, 45, 60],
        preferred_moneyness: Tuple[float, float] = (-0.05, 0.05),  # ATM puts: ±5%
        risk_free_rate: float = 0.05
    ):
        """Initialize protective put strategy.

        Args:
            underlying_symbol: Underlying stock symbol
            signal_generator: Underlying signal generator
            max_position_size: Maximum position size as fraction of portfolio
            preferred_dte: Preferred days to expiration
            preferred_moneyness: Preferred moneyness for puts (ATM percentage)
            risk_free_rate: Risk-free rate
        """
        self.underlying_symbol = underlying_symbol
        self.signal_generator = signal_generator or SignalGenerator()
        self.max_position_size = max_position_size
        self.preferred_dte = preferred_dte
        self.preferred_moneyness = preferred_moneyness  # (min_otm, max_otm) as fraction of stock price
        self.risk_free_rate = risk_free_rate
        self.pricing_model = OptionPricingModel(risk_free_rate)
        self.risk_manager = RiskManager(risk_free_rate)

        logger.info(f"Protective put strategy initialized for {underlying_symbol}")

    def get_underlying_signal(self, market_data: pd.DataFrame, current_date: datetime) -> Optional[Dict]:
        """Get underlying signal from signal generator."""
        signal = self.signal_generator.get_signal(market_data, current_date)
        if signal is None:
            return None

        return {
            'signal_type': signal.signal_type,
            'signal_strength': signal.signal_strength,
            'timestamp': signal.timestamp,
            'metadata': getattr(signal, '__dict__', {})
        }

    def _get_underlying_price(
        self,
        market_data: Optional[pd.DataFrame],
        current_date: datetime
    ) -> Optional[float]:
        """Get current underlying price."""
        if market_data is not None and not market_data.empty:
            if 'adjusted_close' in market_data.columns:
                return float(market_data['adjusted_close'].iloc[-1])
            elif 'close' in market_data.columns:
                return float(market_data['close'].iloc[-1])

        logger.warning("Unable to get underlying price - returning None")
        return None

    def _get_option_mid_price(
        self,
        option_chain: pd.DataFrame,
        option_type: str,
        strike_price: float,
        expiration_date: str
    ) -> Optional[float]:
        """Get mid price for a specific option."""
        matching = option_chain[
            (option_chain['option_type'] == option_type) &
            (abs(option_chain['strike_price'] - strike_price) < 0.25) &
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

    def generate_protective_put_signals(
        self,
        market_data: pd.DataFrame,
        option_chain: pd.DataFrame,
        current_date: Optional[datetime] = None
    ) -> List[Dict]:
        """Generate protective put signals.

        Args:
            market_data: DataFrame with underlying price data
            option_chain: DataFrame with option chain data
            current_date: Current date (None for today)

        Returns:
            List of signal dictionaries
        """
        if current_date is None:
            current_date = datetime.now()

        signals = []

        # Get underlying signal
        underlying_signal = self.get_underlying_signal(market_data, current_date)
        if underlying_signal is None:
            return signals

        # For protective puts, we're typically bullish or neutral
        # We want to own the stock and buy puts for protection
        # Only proceed if we have a bullish or neutral signal
        if underlying_signal['signal_type'] not in ['bullish', 'neutral']:
            logger.debug(f"Signal not suitable for protective put: {underlying_signal['signal_type']}")
            return signals

        # Get underlying price
        underlying_price = self._get_underlying_price(market_data, current_date)
        if underlying_price is None:
            return signals

        # Filter option chain for puts with appropriate DTE
        puts = option_chain[
            (option_chain['option_type'] == 'put') &
            option_chain['expiration_date'].notna()
        ].copy()

        if puts.empty:
            logger.warning("No put options found in chain")
            return signals

        # Calculate days to expiration
        puts['days_to_exp'] = puts['expiration_date'].apply(
            lambda x: (datetime.strptime(x, '%Y-%m-%d') - current_date).days
        )

        # Filter to preferred DTE and future expirations
        puts = puts[
            puts['days_to_exp'].isin(self.preferred_dte) &
            (puts['days_to_exp'] > 0)
        ]

        if puts.empty:
            logger.debug(f"No puts found in preferred DTE range: {self.preferred_dte}")
            return signals

        # Calculate moneyness for each put: (strike - spot) / spot
        # For puts, negative moneyness = OTM, positive = ITM
        puts['moneyness'] = (puts['strike_price'] - underlying_price) / underlying_price

        # Filter to preferred moneyness range (ATM puts)
        min_otm, max_otm = self.preferred_moneyness
        puts = puts[
            (puts['moneyness'] >= min_otm) &
            (puts['moneyness'] <= max_otm)
        ]

        if puts.empty:
            logger.debug(f"No puts found in preferred moneyness range: {self.preferred_moneyness}")
            return signals

        # For each preferred DTE, select best put
        for dte in self.preferred_dte:
            dte_puts = puts[puts['days_to_exp'] == dte].copy()

            if dte_puts.empty:
                continue

            # Select the put with highest premium (or closest to target delta if available)
            dte_puts['mid_price'] = dte_puts.apply(
                lambda row: ((row.get('bid_price', 0) + row.get('ask_price', 0)) / 2
                           if row.get('bid_price') is not None and row.get('ask_price') is not None
                           else row.get('last_price', 0)),
                axis=1
            )

            best_put = dte_puts.loc[dte_puts['mid_price'].idxmax()]

            # Create signal
            signal = {
                'underlying_symbol': self.underlying_symbol,
                'signal_type': 'protective_put',
                'signal_strength': underlying_signal['signal_strength'],
                'underlying_price': underlying_price,
                'put_strike': best_put['strike_price'],
                'put_expiration': best_put['expiration_date'],
                'put_symbol': best_put['option_symbol'],
                'days_to_exp': int(best_put['days_to_exp']),
                'put_mid_price': best_put['mid_price'],
                'timestamp': current_date,
                'underlying_signal': underlying_signal
            }

            signals.append(signal)

        logger.info(f"Generated {len(signals)} protective put signals")
        return signals

    def create_protective_put_position(
        self,
        signal: Dict,
        portfolio_value: float,
        current_date: Optional[datetime] = None
    ) -> Optional[ProtectivePutPosition]:
        """Create a protective put position from a signal.

        Args:
            signal: Signal dictionary from generate_protective_put_signals
            portfolio_value: Current portfolio value
            current_date: Current date (None for today)

        Returns:
            ProtectivePutPosition object or None
        """
        if current_date is None:
            current_date = datetime.now()

        # Extract signal details
        underlying_symbol = signal['underlying_symbol']
        underlying_price = signal['underlying_price']
        put_strike = signal['put_strike']
        put_expiration = signal['put_expiration']
        put_symbol = signal['put_symbol']
        put_price = signal['put_mid_price']

        # For protective put, risk per share is: stock_price + put_price - put_strike
        # This represents the maximum loss per share if stock goes to zero
        risk_per_share = underlying_price + put_price - put_strike

        if risk_per_share <= 0:
            logger.warning(f"Invalid risk per share for protective put: {risk_per_share:.2f}")
            return None

        # Use RiskManager for position sizing based on risk per share
        position_sizing = self.risk_manager.calculate_position_size(
            portfolio_value=portfolio_value,
            risk_per_unit=risk_per_share,
            max_risk_per_trade=self.max_position_size  # Using max_position_size as risk limit
        )

        # Calculate number of shares based on position sizing
        underlying_shares = int(position_sizing.quantity)

        if underlying_shares < 100:  # Minimum 100 shares for 1 contract
            logger.warning(f"Not enough capital for even 1 share lot: {underlying_shares} shares")
            return None

        # Round down to nearest 100 shares (standard option contract size)
        underlying_shares = (underlying_shares // 100) * 100

        if underlying_shares < 100:
            logger.warning(f"Adjusted shares too small: {underlying_shares}")
            return None

        # Number of put contracts to buy (1 contract per 100 shares)
        put_contracts = underlying_shares // 100

        # Calculate actual risk based on the final position size
        actual_risk = underlying_shares * risk_per_share

        # Calculate entry prices
        # In practice, we'd need to get actual fill prices
        stock_entry_price = underlying_price  # Simplified - assumes we buy at market
        put_entry_price = put_price  # Price we pay for buying put

        # Create position
        position = ProtectivePutPosition(
            underlying_symbol=underlying_symbol,
            underlying_quantity=underlying_shares,
            put_symbol=put_symbol,
            put_strike=put_strike,
            put_expiration=put_expiration,
            put_quantity=put_contracts,  # Positive because we're long puts
            entry_date=current_date,
            stock_entry_price=stock_entry_price,
            put_entry_price=put_entry_price,
            max_profit=0,  # Will be calculated in __post_init__
            max_loss=0,    # Will be calculated in __post_init__
            breakeven=0    # Will be calculated in __post_init__
        )

        logger.info(
            f"Created protective put: {underlying_shares} shares {underlying_symbol} "
            f"@ ${stock_entry_price:.2f} + {put_contracts} PUT {put_symbol} "
            f"strike ${put_strike:.2f} exp {put_expiration} "
            f"debit: ${put_entry_price:.2f}"
        )

        return position

    def exit_protective_put(
        self,
        position: ProtectivePutPosition,
        market_data: Optional[pd.DataFrame],
        option_chain: pd.DataFrame,
        current_date: datetime
    ) -> Tuple[bool, float, str]:
        """Determine if a protective put should be exited.

        Args:
            position: Current protective put position
            market_data: Current market data for underlying
            option_chain: Current option chain data
            current_date: Current date

        Returns:
            Tuple of (should_exit, exit_value, reason)
        """
        # Check if expired
        exp_date = datetime.strptime(position.put_expiration, '%Y-%m-%d')
        days_to_exp = (exp_date - current_date).days

        if days_to_exp <= 0:
            # Option has expired - calculate settlement
            return self._calculate_protective_put_expiration(position, exp_date, market_data)

        # Get current prices
        underlying_price = self._get_underlying_price(market_data, current_date)
        if underlying_price is None:
            logger.warning("Could not get underlying price for exit calculation")
            return False, 0.0, "Missing underlying price"

        # Get current put price
        put_mid = self._get_option_mid_price(
            option_chain,
            'put',
            position.put_strike,
            position.put_expiration
        )

        if put_mid is None:
            logger.warning("Could not get put price for exit calculation")
            return False, 0.0, "Missing put price"

        # Calculate current position value
        # Stock value
        stock_value = position.underlying_quantity * underlying_price

        # Put value (we are long, so positive)
        put_value = put_mid * 100 * position.put_quantity

        # Total position value if we liquidated
        liquidation_value = stock_value + put_value

        # Calculate original cost
        stock_cost = position.underlying_quantity * position.stock_entry_price
        put_cost = position.put_entry_price * 100 * position.put_quantity
        original_cost = stock_cost + put_cost

        # Current P&L
        current_pnl = liquidation_value - original_cost

        # Exit conditions
        # 1. Take profit at 20% of position value
        # For protective puts, we might exit if we've made good profits
        if current_pnl >= 0.2 * original_cost:  # 20% profit target
            return True, liquidation_value, f"Take profit reached ({current_pnl:.2f})"

        # 2. Stop loss - if put has lost significant time value
        # Exit if put value has decayed significantly
        original_put_value = position.put_entry_price * 100 * position.put_quantity
        if put_mid < (original_put_value * 0.1):  # Put worth less than 10% of original value
            return True, liquidation_value, f"Put value decayed (<10% of original)"

        # 3. Time decay - exit if too close to expiration
        if days_to_exp <= 7:
            return True, liquidation_value, f"Time decay exit ({days_to_exp} days to exp)"

        # 4. Stock price well above breakeven (protection no longer needed cost-effectively)
        if underlying_price >= position.breakeven * 1.5:  # 50% above breakeven
            return True, liquidation_value, f"Stock well above breakeven ({underlying_price:.2f} >= {position.breakeven * 1.5:.2f})"

        return False, liquidation_value, "Hold position"

    def _calculate_protective_put_expiration(
        self,
        position: ProtectivePutPosition,
        expiration_date: datetime,
        market_data: Optional[pd.DataFrame] = None
    ) -> Tuple[bool, float, str]:
        """Calculate protective put value at expiration.

        Args:
            position: Protective put position
            expiration_date: Expiration date
            market_data: Market data for underlying (used to get settlement price)

        Returns:
            Tuple of (should_exit, expiration_value, reason)
        """
        # At expiration, we need the underlying settlement price
        # Get it from market data if available, otherwise fall back to current price
        if market_data is not None and not market_data.empty:
            # Try to get the settlement price for the expiration date
            # For simplicity, we'll use the most recent price available
            # In a more sophisticated implementation, we'd look for the exact expiration date price
            underlying_settlement_price = self._get_underlying_price(market_data, expiration_date)
            if underlying_settlement_price is None:
                # Fall back to current price if we can't get historical price
                underlying_settlement_price = underlying_price
                logger.warning(
                    f"Could not get settlement price for {position.underlying_symbol} on "
                    f"{expiration_date.strftime('%Y-%m-%d')}, using current price as approximation"
                )
        else:
            # Fall back to current price if no market data available
            underlying_settlement_price = underlying_price
            logger.warning(
                f"No market data available for {position.underlying_symbol}, "
                f"using current price as approximation for settlement price"
            )

        # Stock value at settlement
        stock_value = position.underlying_quantity * underlying_settlement_price

        # Put value at expiration
        # If stock price < strike, put is ITM and we can exercise to sell at strike
        # If stock price >= strike, put expires worthless
        if underlying_settlement_price < position.put_strike:
            # Put is ITM: exercise to sell stock at strike price
            put_value = position.put_strike * 100 * position.put_quantity
        else:
            # Put expires worthless
            put_value = 0

        # Total position value at expiration
        expiration_value = stock_value + put_value

        # Original cost
        stock_cost = position.underlying_quantity * position.stock_entry_price
        put_cost = position.put_entry_price * 100 * position.put_quantity
        original_cost = stock_cost + put_cost

        # P&L at expiration
        pnl_at_expiration = expiration_value - original_cost

        logger.info(
            f"Protective put expired. Underlying settlement: ${underlying_settlement_price:.2f}, "
            f"Position value: ${expiration_value:.2f}, Original cost: ${original_cost:.2f}, "
            f"P&L: ${pnl_at_expiration:.2f}"
        )

        return True, expiration_value, f"Expired at {expiration_date.strftime('%Y-%m-%d')}"


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
    for strike in [140, 145, 150, 155, 160, 165, 170]:
        # Call option
        sample_data.append({
            'option_symbol': f'AAPL{base_date.strftime("%y%m%d")}C{int(strike*1000):08d}',
            'underlying_symbol': 'AAPL',
            'expiration_date': exp_date,
            'option_type': 'call',
            'strike_price': strike,
            'bid_price': max(0, underlying_price - strike + 5.0) * 0.8,
            'ask_price': max(0, underlying_price - strike + 5.0) * 0.9,
            'last_price': max(0, underlying_price - strike + 5.0) * 0.85,
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
            'bid_price': max(0, strike - underlying_price + 5.0) * 0.8,
            'ask_price': max(0, strike - underlying_price + 5.0) * 0.9,
            'last_price': max(0, strike - underlying_price + 5.0) * 0.85,
            'volume': 100,
            'open_interest': 500
        })

    option_chain = pd.DataFrame(sample_data)

    # Create sample market data
    market_data = pd.DataFrame({
        'date': [datetime.now() - timedelta(days=i) for i in range(10, 0, -1)],
        'adjusted_close': [148, 149, 150, 151, 152, 153, 154, 155, 156, 157],
        'volume': [1000000] * 10
    })

    # Test protective put strategy
    logger.info("=== Testing Protective Put Strategy ===")
    pp_strategy = ProtectivePutStrategy('AAPL')
    pp_signals = pp_strategy.generate_protective_put_signals(market_data, option_chain)

    logger.info(f"Generated {len(pp_signals)} protective put signals")
    if pp_signals:
        signal = pp_signals[0]
        logger.debug(f"Signal: {signal}")

        # Create position
        position = pp_strategy.create_protective_put_position(signal, portfolio_value=100000)
        if position:
            logger.debug(f"Created position: {position}")

            # Check exit condition
            should_exit, exit_value, reason = pp_strategy.exit_protective_put(
                position, market_data, option_chain, datetime.now()
            )
            logger.debug(f"Exit recommendation: {should_exit} - {reason}")
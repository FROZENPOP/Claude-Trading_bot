"""Covered call and cash-secured put strategy implementations."""

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
class CoveredCallPosition:
    """Represents a covered call position."""
    underlying_symbol: str
    underlying_quantity: int  # Number of shares owned
    call_symbol: str
    call_strike: float
    call_expiration: str
    call_quantity: int  # Number of call contracts sold (negative)
    entry_date: datetime
    stock_entry_price: float  # Average price paid for stock
    call_entry_price: float  # Price received for selling call
    max_profit: float
    max_loss: float
    breakeven: float

    def __post_init__(self):
        """Calculate derived values after initialization."""
        # Max profit: stock appreciation to strike + call premium received
        stock_gain = max(0, (self.call_strike - self.stock_entry_price)) * self.underlying_quantity
        call_credit = abs(self.call_entry_price) * 100 * abs(self.call_quantity)
        self.max_profit = stock_gain + call_credit

        # Max loss: stock goes to zero minus call premium received
        stock_loss = self.stock_entry_price * self.underlying_quantity
        self.max_loss = stock_loss - call_credit

        # Breakeven: stock price where total P&L = 0
        # (Stock loss) + (Call credit) = 0 at breakeven
        # Stock loss at breakeven = (stock_entry_price - breakeven_price) * quantity
        # So: (stock_entry_price - breakeven_price) * quantity + call_credit = 0
        # breakeven_price = stock_entry_price + (call_credit / quantity)
        if self.underlying_quantity != 0:
            call_credit_per_share = abs(self.call_entry_price) * 100 * abs(self.call_quantity) / self.underlying_quantity
            self.breakeven = self.stock_entry_price - call_credit_per_share
        else:
            self.breakeven = 0


@dataclass
class CashSecuredPutPosition:
    """Represents a cash-secured put position."""
    underlying_symbol: str
    put_symbol: str
    put_strike: float
    put_expiration: str
    put_quantity: int  # Number of put contracts sold (negative)
    entry_date: datetime
    cash_secured: float  # Cash set aside to buy shares if assigned
    put_entry_price: float  # Price received for selling put
    max_profit: float
    max_loss: float
    breakeven: float

    def __post_init__(self):
        """Calculate derived values after initialization."""
        # Max profit: put premium received
        self.max_profit = abs(self.put_entry_price) * 100 * abs(self.put_quantity)

        # Max loss: strike price minus put premium received (put goes deep ITM)
        # We're obligated to buy at strike, but we keep the premium
        self.max_loss = (self.put_strike * 100 * abs(self.put_quantity)) - self.max_profit

        # Breakeven: stock price where total P&L = 0
        # At breakeven: put expires worthless, we keep premium
        # If stock < breakeven at expiration, we lose money on the put
        # Actually, for cash-secured put, breakeven = strike - premium received
        # Because we effectively pay (strike - premium) if assigned
        self.breakeven = self.put_strike - (abs(self.put_entry_price) * 100)


class BaseOptionStrategy:
    """Base class for option strategies that combine underlying positions with options."""

    def __init__(
        self,
        underlying_symbol: str,
        signal_generator: Optional[SignalGenerator] = None,
        risk_free_rate: float = 0.05
    ):
        """Initialize base option strategy.

        Args:
            underlying_symbol: Underlying stock symbol
            signal_generator: Underlying signal generator
            risk_free_rate: Risk-free rate for pricing models
        """
        self.underlying_symbol = underlying_symbol
        self.signal_generator = signal_generator or SignalGenerator()
        self.risk_free_rate = risk_free_rate
        self.pricing_model = OptionPricingModel(risk_free_rate)

        logger.info(f"{self.__class__.__name__} initialized for {underlying_symbol}")

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


class CoveredCallStrategy(BaseOptionStrategy):
    """Covered call strategy: long stock + short call."""

    def __init__(
        self,
        underlying_symbol: str,
        signal_generator: Optional[SignalGenerator] = None,
        max_position_size: float = 0.10,  # 10% of portfolio per trade
        preferred_dte: List[int] = [21, 30, 45, 60],
        preferred_moneyness: Tuple[float, float] = (0.0, 0.10),  # OTM calls: 0% to 10% OTM
        risk_free_rate: float = 0.05
    ):
        """Initialize covered call strategy.

        Args:
            underlying_symbol: Underlying stock symbol
            signal_generator: Underlying signal generator
            max_position_size: Maximum position size as fraction of portfolio
            preferred_dte: Preferred days to expiration
            preferred_moneyness: Preferred moneyness for calls (OTM percentage)
            risk_free_rate: Risk-free rate
        """
        super().__init__(underlying_symbol, signal_generator, risk_free_rate)
        self.max_position_size = max_position_size
        self.preferred_dte = preferred_dte
        self.preferred_moneyness = preferred_moneyness  # (min_otm, max_otm) as fraction of stock price

        logger.info(f"Covered call strategy initialized for {underlying_symbol}")

    def generate_covered_call_signals(
        self,
        market_data: pd.DataFrame,
        option_chain: pd.DataFrame,
        current_date: Optional[datetime] = None
    ) -> List[Dict]:
        """Generate covered call signals.

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

        # For covered calls, we're typically neutral to slightly bullish
        # We want to own the stock and sell calls against it
        # Only proceed if we have a neutral or bullish signal
        if underlying_signal['signal_type'] not in ['bullish', 'neutral']:
            logger.debug(f"Signal not suitable for covered call: {underlying_signal['signal_type']}")
            return signals

        # Get underlying price
        underlying_price = self._get_underlying_price(market_data, current_date)
        if underlying_price is None:
            return signals

        # Filter option chain for calls with appropriate DTE
        calls = option_chain[
            (option_chain['option_type'] == 'call') &
            option_chain['expiration_date'].notna()
        ].copy()

        if calls.empty:
            logger.warning("No call options found in chain")
            return signals

        # Calculate days to expiration
        calls['days_to_exp'] = calls['expiration_date'].apply(
            lambda x: (datetime.strptime(x, '%Y-%m-%d') - current_date).days
        )

        # Filter to preferred DTE and future expirations
        calls = calls[
            calls['days_to_exp'].isin(self.preferred_dte) &
            (calls['days_to_exp'] > 0)
        ]

        if calls.empty:
            logger.debug(f"No calls found in preferred DTE range: {self.preferred_dte}")
            return signals

        # Calculate moneyness for each call: (strike - spot) / spot
        calls['moneyness'] = (calls['strike_price'] - underlying_price) / underlying_price

        # Filter to preferred moneyness range (OTM calls)
        min_otm, max_otm = self.preferred_moneyness
        calls = calls[
            (calls['moneyness'] >= min_otm) &
            (calls['moneyness'] <= max_otm)
        ]

        if calls.empty:
            logger.debug(f"No calls found in preferred moneyness range: {self.preferred_moneyness}")
            return signals

        # For each preferred DTE, select best call
        for dte in self.preferred_dte:
            dte_calls = calls[calls['days_to_exp'] == dte].copy()

            if dte_calls.empty:
                continue

            # Select the call with highest premium (or closest to target delta if available)
            # For simplicity, we'll use the one with highest bid/ask midpoint
            dte_calls['mid_price'] = dte_calls.apply(
                lambda row: ((row.get('bid_price', 0) + row.get('ask_price', 0)) / 2
                           if row.get('bid_price') is not None and row.get('ask_price') is not None
                           else row.get('last_price', 0)),
                axis=1
            )

            best_call = dte_calls.loc[dte_calls['mid_price'].idxmax()]

            # Create signal
            signal = {
                'underlying_symbol': self.underlying_symbol,
                'signal_type': 'covered_call',
                'signal_strength': underlying_signal['signal_strength'],
                'underlying_price': underlying_price,
                'call_strike': best_call['strike_price'],
                'call_expiration': best_call['expiration_date'],
                'call_symbol': best_call['option_symbol'],
                'days_to_exp': int(best_call['days_to_exp']),
                'call_mid_price': best_call['mid_price'],
                'timestamp': current_date,
                'underlying_signal': underlying_signal
            }

            signals.append(signal)

        logger.info(f"Generated {len(signals)} covered call signals")
        return signals

    def create_covered_call_position(
        self,
        signal: Dict,
        portfolio_value: float,
        current_date: Optional[datetime] = None
    ) -> Optional[CoveredCallPosition]:
        """Create a covered call position from a signal.

        Args:
            signal: Signal dictionary from generate_covered_call_signals
            portfolio_value: Current portfolio value
            current_date: Current date (None for today)

        Returns:
            CoveredCallPosition object or None
        """
        if current_date is None:
            current_date = datetime.now()

        # Extract signal details
        underlying_symbol = signal['underlying_symbol']
        underlying_price = signal['underlying_price']
        call_strike = signal['call_strike']
        call_expiration = signal['call_expiration']
        call_symbol = signal['call_symbol']
        call_price = signal['call_mid_price']

        # Calculate how many shares we can buy (position sizing)
        max_stock_value = portfolio_value * self.max_position_size
        underlying_shares = int(max_stock_value / underlying_price)

        if underlying_shares < 100:  # Minimum 100 shares for 1 contract
            logger.warning(f"Not enough capital for even 1 share lot: {underlying_shares} shares")
            return None

        # Round down to nearest 100 shares (standard option contract size)
        underlying_shares = (underlying_shares // 100) * 100

        if underlying_shares < 100:
            logger.warning(f"Adjusted shares too small: {underlying_shares}")
            return None

        # Number of call contracts to sell (1 contract per 100 shares)
        call_contracts = underlying_shares // 100

        # Calculate entry prices
        # In practice, we'd need to get actual fill prices
        stock_entry_price = underlying_price  # Simplified - assumes we buy at market
        call_entry_price = call_price  # Price we receive for selling call

        # Create position
        position = CoveredCallPosition(
            underlying_symbol=underlying_symbol,
            underlying_quantity=underlying_shares,
            call_symbol=call_symbol,
            call_strike=call_strike,
            call_expiration=call_expiration,
            call_quantity=-call_contracts,  # Negative because we're short calls
            entry_date=current_date,
            stock_entry_price=stock_entry_price,
            call_entry_price=call_entry_price,
            max_profit=0,  # Will be calculated in __post_init__
            max_loss=0,    # Will be calculated in __post_init__
            breakeven=0    # Will be calculated in __post_init__
        )

        logger.info(
            f"Created covered call: {underlying_shares} shares {underlying_symbol} "
            f"@ ${stock_entry_price:.2f} + {call_contracts} CALL {call_symbol} "
            f"strike ${call_strike:.2f} exp {call_expiration} "
            f"credit: ${call_entry_price:.2f}"
        )

        return position

    def exit_covered_call(
        self,
        position: CoveredCallPosition,
        market_data: Optional[pd.DataFrame],
        option_chain: pd.DataFrame,
        current_date: datetime
    ) -> Tuple[bool, float, str]:
        """Determine if a covered call should be exited.

        Args:
            position: Current covered call position
            market_data: Current market data for underlying
            option_chain: Current option chain data
            current_date: Current date

        Returns:
            Tuple of (should_exit, exit_value, reason)
        """
        # Check if expired
        exp_date = datetime.strptime(position.call_expiration, '%Y-%m-%d')
        days_to_exp = (exp_date - current_date).days

        if days_to_exp <= 0:
            # Option has expired - calculate settlement
            return self._calculate_covered_call_expiration(position, exp_date, market_data)

        # Get current prices
        underlying_price = self._get_underlying_price(market_data, current_date)
        if underlying_price is None:
            logger.warning("Could not get underlying price for exit calculation")
            return False, 0.0, "Missing underlying price"

        # Get current call price
        call_mid = self._get_option_mid_price(
            option_chain,
            'call',
            position.call_strike,
            position.call_expiration
        )

        if call_mid is None:
            logger.warning("Could not get call price for exit calculation")
            return False, 0.0, "Missing call price"

        # Calculate current position value
        # Stock value
        stock_value = position.underlying_quantity * underlying_price

        # Call value (we are short, so negative)
        call_value = call_mid * 100 * abs(position.call_quantity)  # Positive value we would pay to buy back

        # Total position value if we liquidated
        liquidation_value = stock_value - call_value

        # Calculate original cost
        stock_cost = position.underlying_quantity * position.stock_entry_price
        call_credit = abs(position.call_entry_price) * 100 * abs(position.call_quantity)
        original_cost = stock_cost - call_credit  # Net cost to establish position

        # Current P&L
        current_pnl = liquidation_value - original_cost

        # Exit conditions
        # 1. Take profit at 50% of max profit
        if current_pnl >= 0.5 * position.max_profit:
            return True, liquidation_value, f"Take profit reached ({current_pnl:.2f})"

        # 2. Stop loss at 50% of max loss
        if current_pnl <= -0.5 * position.max_loss:
            return True, liquidation_value, f"Stop loss triggered ({current_pnl:.2f})"

        # 3. Time decay - exit if too close to expiration
        if days_to_exp <= 7:
            return True, liquidation_value, f"Time decay exit ({days_to_exp} days to exp)"

        # 4. Stock price breached strike (call is ITM and likely to be assigned)
        if underlying_price >= position.call_strike:
            return True, liquidation_value, f"Stock price >= strike ({underlying_price:.2f} >= {position.call_strike:.2f})"

        return False, liquidation_value, "Hold position"

    def _calculate_covered_call_expiration(
        self,
        position: CoveredCallPosition,
        expiration_date: datetime,
        market_data: Optional[pd.DataFrame] = None
    ) -> Tuple[bool, float, str]:
        """Calculate covered call value at expiration.

        Args:
            position: Covered call position
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

        # Call value at expiration
        # If stock price >= strike, call is exercised and we sell stock at strike
        # If stock price < strike, call expires worthless
        if underlying_settlement_price >= position.call_strike:
            # Call is exercised: we sell stock at strike price
            call_value = position.call_strike * 100 * abs(position.call_quantity)
            # Note: stock_value above is what we keep, but we deliver shares at strike
            # So we effectively receive strike price for our shares
            effective_stock_value = position.call_strike * position.underlying_quantity
        else:
            # Call expires worthless
            call_value = 0
            effective_stock_value = stock_value  # We keep the stock

        # Total position value at expiration
        expiration_value = effective_stock_value  # We don't double count - either we have stock or cash from sale

        # Original cost
        stock_cost = position.underlying_quantity * position.stock_entry_price
        call_credit = abs(position.call_entry_price) * 100 * abs(position.call_quantity)
        original_net_cost = stock_cost - call_credit

        # P&L at expiration
        pnl_at_expiration = expiration_value - original_net_cost

        logger.info(
            f"Covered call expired. Underlying settlement: ${underlying_settlement_price:.2f}, "
            f"Position value: ${expiration_value:.2f}, Original net cost: ${original_net_cost:.2f}, "
            f"P&L: ${pnl_at_expiration:.2f}"
        )

        return True, expiration_value, f"Expired at {expiration_date.strftime('%Y-%m-%d')}"


class CashSecuredPutStrategy(BaseOptionStrategy):
    """Cash-secured put strategy: short put + cash set aside to buy shares."""

    def __init__(
        self,
        underlying_symbol: str,
        signal_generator: Optional[SignalGenerator] = None,
        max_position_size: float = 0.10,  # 10% of portfolio per trade
        preferred_dte: List[int] = [21, 30, 45, 60],
        preferred_moneyness: Tuple[float, float] = (-0.10, 0.0),  # OTM to ATM puts: -10% to 0%
        risk_free_rate: float = 0.05
    ):
        """Initialize cash-secured put strategy.

        Args:
            underlying_symbol: Underlying stock symbol
            signal_generator: Underlying signal generator
            max_position_size: Maximum position size as fraction of portfolio
            preferred_dte: Preferred days to expiration
            preferred_moneyness: Preferred moneyness for puts (OTM/ATM percentage)
            risk_free_rate: Risk-free rate
        """
        super().__init__(underlying_symbol, signal_generator, risk_free_rate)
        self.max_position_size = max_position_size
        self.preferred_dte = preferred_dte
        self.preferred_moneyness = preferred_moneyness  # (min_otm, max_otm) as fraction of stock price

        logger.info(f"Cash-secured put strategy initialized for {underlying_symbol}")

    def generate_cash_secured_put_signals(
        self,
        market_data: pd.DataFrame,
        option_chain: pd.DataFrame,
        current_date: Optional[datetime] = None
    ) -> List[Dict]:
        """Generate cash-secured put signals.

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

        # For cash-secured puts, we're typically neutral to slightly bearish
        # We want to be willing to own the stock at the strike price
        # Only proceed if we have a neutral or bearish signal
        if underlying_signal['signal_type'] not in ['bearish', 'neutral']:
            logger.debug(f"Signal not suitable for cash-secured put: {underlying_signal['signal_type']}")
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

        # Filter to preferred moneyness range (OTM to ATM puts)
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
                'signal_type': 'cash_secured_put',
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

        logger.info(f"Generated {len(signals)} cash-secured put signals")
        return signals

    def create_cash_secured_put_position(
        self,
        signal: Dict,
        portfolio_value: float,
        current_date: Optional[datetime] = None
    ) -> Optional[CashSecuredPutPosition]:
        """Create a cash-secured put position from a signal.

        Args:
            signal: Signal dictionary from generate_cash_secured_put_signals
            portfolio_value: Current portfolio value
            current_date: Current date (None for today)

        Returns:
            CashSecuredPutPosition object or None
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

        # Calculate how much cash we need to secure (enough to buy 100 shares per contract at strike)
        max_put_value = portfolio_value * self.max_position_size

        # Each put contract requires cash for 100 shares at strike price
        cash_per_contract = put_strike * 100
        max_contracts = int(max_put_value / cash_per_contract)

        if max_contracts < 1:
            logger.warning(f"Not enough capital for even 1 put contract: need ${cash_per_contract:.2f}")
            return None

        # Use maximum contracts we can afford
        put_contracts = max_contracts

        # Calculate entry prices
        stock_entry_price = underlying_price  # Simplified
        put_entry_price = put_price  # Price we receive for selling put

        # Create position
        position = CashSecuredPutPosition(
            underlying_symbol=underlying_symbol,
            put_symbol=put_symbol,
            put_strike=put_strike,
            put_expiration=put_expiration,
            put_quantity=-put_contracts,  # Negative because we're short puts
            entry_date=current_date,
            cash_secured=cash_per_contract * put_contracts,
            put_entry_price=put_entry_price,
            max_profit=0,  # Will be calculated in __post_init__
            max_loss=0,    # Will be calculated in __post_init__
            breakeven=0    # Will be calculated in __post_init__
        )

        logger.info(
            f"Created cash-secured put: {put_contracts} PUT {put_symbol} "
            f"strike ${put_strike:.2f} exp {put_expiration} "
            f"credit: ${put_entry_price:.2f} secured: ${position.cash_secured:.2f}"
        )

        return position

    def exit_cash_secured_put(
        self,
        position: CashSecuredPutPosition,
        market_data: Optional[pd.DataFrame],
        option_chain: pd.DataFrame,
        current_date: datetime
    ) -> Tuple[bool, float, str]:
        """Determine if a cash-secured put should be exited.

        Args:
            position: Current cash-secured put position
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
            return self._calculate_cash_secured_put_expiration(position, exp_date, market_data)

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
        # We are short the put, so position value is negative of put value
        put_value = put_mid * 100 * abs(position.put_quantity)  # What we would pay to buy back
        cash_value = position.cash_secured  # Cash we have set aside

        # Net position value (what we could liquidate for)
        liquidation_value = cash_value - put_value

        # Original credit received
        original_credit = abs(position.put_entry_price) * 100 * abs(position.put_quantity)

        # Current P&L (we keep the credit minus cost to close)
        current_pnl = original_credit - put_value

        # Exit conditions
        # 1. Take profit at 50% of max profit
        if current_pnl >= 0.5 * position.max_profit:
            return True, liquidation_value, f"Take profit reached ({current_pnl:.2f})"

        # 2. Stop loss - if put value exceeds our credit (we're losing money)
        if put_value > original_credit:
            return True, liquidation_value, f"Put value exceeds credit ({put_value:.2f} > {original_credit:.2f})"

        # 3. Time decay - exit if too close to expiration
        if days_to_exp <= 7:
            return True, liquidation_value, f"Time decay exit ({days_to_exp} days to exp)"

        # 4. Stock price well above strike (put is deep OTM, unlikely to be assigned)
        if underlying_price >= position.put_strike * 1.2:  # 20% above strike
            return True, liquidation_value, f"Stock well above strike ({underlying_price:.2f} >= {position.put_strike * 1.2:.2f})"

        return False, liquidation_value, "Hold position"

    def _calculate_cash_secured_put_expiration(
        self,
        position: CashSecuredPutPosition,
        expiration_date: datetime,
        market_data: Optional[pd.DataFrame] = None
    ) -> Tuple[bool, float, str]:
        """Calculate cash-secured put value at expiration.

        Args:
            position: Cash-secured put position
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

        # Cash we have set aside
        cash_value = position.cash_secured

        # Put value at expiration
        # If stock price < strike, put is assigned and we buy stock at strike
        # If stock price >= strike, put expires worthless
        if underlying_settlement_price < position.put_strike:
            # Put is assigned: we buy stock at strike price
            stock_value = underlying_settlement_price * (position.cash_secured / position.put_strike)
            # Actually, we use our cash to buy shares at strike
            # Number of shares we can buy = cash_secured / put_strike
            shares_bought = position.cash_secured / position.put_strike
            stock_value = shares_bought * underlying_settlement_price
            # We have stock worth stock_value, but we spent cash_secured to get it
            # So our net position is the stock we own
            expiration_value = stock_value
        else:
            # Put expires worthless, we keep our cash
            expiration_value = cash_value

        # Original credit received
        original_credit = abs(position.put_entry_price) * 100 * abs(position.put_quantity)

        # P&L at expiration
        pnl_at_expiration = expiration_value - 0  # We started with zero position, ended with expiration_value
        # Actually, we received original_credit cash upfront, and now have expiration_value
        # So total P&L = original_credit + (expiration_value - cash_secured)
        # But cash_secured was set aside from original capital, so it's not a profit/loss item
        # Better way: we received credit, and now we have either stock or cash
        total_value_now = expiration_value
        # We originally received credit and set aside cash_secured
        # If put expired worthless: we have cash_secured + credit
        # If put was assigned: we have stock worth expiration_value
        if underlying_settlement_price >= position.put_strike:
            # Put expired worthless
            pnl_at_expiration = original_credit  # We keep the credit
        else:
            # Put was assigned
            # We used cash_secured to buy stock, now worth stock_value
            # We also keep the credit
            pnl_at_expiration = original_credit + (expiration_value - position.cash_secured)

        logger.info(
            f"Cash-secured put expired. Underlying settlement: ${underlying_settlement_price:.2f}, "
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
    base_date = datetime.now() + timedelta(days=30)
    exp_date = base_date.strftime('%Y-%m-%d')

    # Generate sample calls and puts around ATM
    underlying_price = 150.0
    for strike in [145, 147.5, 150, 152.5, 155, 157.5, 160]:
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
            'bid_price': max(0, strike - underlying_price + 2.0) * 0.8,
            'ask_price': max(0, strike - underlying_price + 2.0) * 0.9,
            'last_price': max(0, strike - underlying_price + 2.0) * 0.85,
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

    # Test covered call strategy
    print("=== Testing Covered Call Strategy ===")
    cc_strategy = CoveredCallStrategy('AAPL')
    cc_signals = cc_strategy.generate_covered_call_signals(market_data, option_chain)

    print(f"Generated {len(cc_signals)} covered call signals")
    if cc_signals:
        signal = cc_signals[0]
        print(f"Signal: {signal}")

        # Create position
        position = cc_strategy.create_covered_call_position(signal, portfolio_value=100000)
        if position:
            print(f"Created position: {position}")

            # Check exit condition
            should_exit, exit_value, reason = cc_strategy.exit_covered_call(
                position, market_data, option_chain, datetime.now()
            )
            print(f"Exit recommendation: {should_exit} - {reason}")

    print("\n=== Testing Cash-Secured Put Strategy ===")
    # Test cash-secured put strategy
    csp_strategy = CashSecuredPutStrategy('AAPL')
    csp_signals = csp_strategy.generate_cash_secured_put_signals(market_data, option_chain)

    print(f"Generated {len(csp_signals)} cash-secured put signals")
    if csp_signals:
        signal = csp_signals[0]
        print(f"Signal: {signal}")

        # Create position
        position = csp_strategy.create_cash_secured_put_position(signal, portfolio_value=100000)
        if position:
            print(f"Created position: {position}")

            # Check exit condition
            should_exit, exit_value, reason = csp_strategy.exit_cash_secured_put(
                position, market_data, option_chain, datetime.now()
            )
            print(f"Exit recommendation: {should_exit} - {reason}")
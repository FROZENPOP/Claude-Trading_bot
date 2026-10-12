"""Portfolio risk management module with options support."""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class RiskLimits:
    """Risk limits configuration."""
    target_volatility: float = 0.15  # 15% annualized
    max_position_size: float = 0.10  # 10% of portfolio
    max_portfolio_exposure: float = 1.0  # 100%
    max_daily_loss: float = 0.05  # 5% of portfolio
    max_drawdown: float = 0.15  # 15% drawdown
    max_open_positions: int = 10
    max_daily_trades: int = 10

    # Options-specific risk limits
    max_option_notional: float = 0.50  # 50% of portfolio in option notional
    max_net_delta: float = 0.20  # 20% delta exposure
    max_gamma_exposure: float = 0.05  # 5% gamma exposure
    max_theta_decay: float = 0.02  # 2% daily theta decay
    max_vega_exposure: float = 0.10  # 10% vega exposure
    max_single_option_position: float = 0.15  # 15% of portfolio per option position


@dataclass
class PortfolioGreeks:
    """Portfolio-level Greeks for options positions."""
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0

    def __add__(self, other):
        """Add two PortfolioGreeks objects."""
        return PortfolioGreeks(
            delta=self.delta + other.delta,
            gamma=self.gamma + other.gamma,
            theta=self.theta + other.theta,
            vega=self.vega + other.vega,
            rho=self.rho + other.rho
        )

    def __sub__(self, other):
        """Subtract two PortfolioGreeks objects."""
        return PortfolioGreeks(
            delta=self.delta - other.delta,
            gamma=self.gamma - other.gamma,
            theta=self.theta - other.theta,
            vega=self.vega - other.vega,
            rho=self.rho - other.rho
        )


@dataclass
class OptionPosition:
    """Represents an options position."""
    symbol: str
    option_symbol: str
    quantity: float  # Number of contracts
    strike: float
    expiration: str
    option_type: str  # 'call' or 'put'
    entry_price: float
    current_price: float
    underlying_price: float
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0

    def get_market_value(self) -> float:
        """Get current market value of the position."""
        return abs(self.quantity * self.current_price * 100)  # Options are 100 shares per contract

    def get_notional_value(self) -> float:
        """Get notional value (exposure to underlying)."""
        return abs(self.quantity * self.underlying_price * 100)

    def get_position_greeks(self) -> PortfolioGreeks:
        """Get Greeks for this position."""
        # Greeks are typically per share, so multiply by 100 for contract size and quantity
        return PortfolioGreeks(
            delta=self.delta * self.quantity * 100,
            gamma=self.gamma * self.quantity * 100,
            theta=self.theta * self.quantity * 100,
            vega=self.vega * self.quantity * 100,
            rho=self.rho * self.quantity * 100
        )


class RiskChecker:
    """Check if trades comply with risk limits."""

    def __init__(self, limits: RiskLimits):
        """Initialize risk checker.

        Args:
            limits: Risk limits configuration
        """
        self.limits = limits
        self.daily_loss = 0.0
        self.daily_trades = 0
        self.peak_value = None
        self.current_drawdown = 0
        self.portfolio_greeks = PortfolioGreeks()
        self.total_option_notional = 0.0

    def check_position_limit(
        self,
        portfolio_value: float,
        current_positions: dict,
        new_position_value: float
    ) -> tuple[bool, str]:
        """Check if adding a position would exceed limits.

        Args:
            portfolio_value: Total portfolio value
            current_positions: Current position dictionary
            new_position_value: Value of new position

        Returns:
            Tuple of (passes, reason)
        """
        total_exposure = sum(p.get_value(p.price) for p in current_positions.values())
        total_exposure += new_position_value

        # Check max portfolio exposure
        if total_exposure > portfolio_value * self.limits.max_portfolio_exposure:
            return False, f"Exceeds max exposure ({total_exposure/portfolio_value:.1%} > {self.limits.max_portfolio_exposure:.1%})"

        # Check max position size
        if new_position_value > portfolio_value * self.limits.max_position_size:
            return False, f"Position exceeds max size ({new_position_value/portfolio_value:.1%} > {self.limits.max_position_size:.1%})"

        # Check max open positions
        if len(current_positions) >= self.limits.max_open_positions:
            return False, f"Exceeds max positions ({len(current_positions)} >= {self.limits.max_open_positions})"

        return True, "OK"

    def check_daily_loss_limit(self, portfolio_value: float, new_value: float) -> tuple[bool, float]:
        """Check if daily loss would exceed limit.

        Args:
            portfolio_value: Current portfolio value
            new_value: New portfolio value after potential loss

        Returns:
            Tuple of (passes, daily_loss_amount)
        """
        daily_loss = (portfolio_value - new_value) / portfolio_value if portfolio_value > 0 else 0

        if daily_loss > self.limits.max_daily_loss:
            return False, daily_loss

        return True, daily_loss

    def check_drawdown_limit(self, portfolio_value: float) -> tuple[bool, float]:
        """Check if current drawdown exceeds limit.

        Args:
            portfolio_value: Current portfolio value

        Returns:
            Tuple of (passes, current_drawdown)
        """
        if self.peak_value is None:
            self.peak_value = portfolio_value
        else:
            self.peak_value = max(self.peak_value, portfolio_value)

        self.current_drawdown = (self.peak_value - portfolio_value) / self.peak_value if self.peak_value > 0 else 0

        if self.current_drawdown > self.limits.max_drawdown:
            return False, self.current_drawdown

        return True, self.current_drawdown

    def check_daily_trades_limit(self) -> tuple[bool, int]:
        """Check if daily trade limit would be exceeded.

        Returns:
            Tuple of (passes, current_trades)
        """
        if self.daily_trades >= self.limits.max_daily_trades:
            return False, self.daily_trades

        return True, self.daily_trades

    def update_daily_loss(self, loss: float):
        """Update daily loss counter.

        Args:
            loss: Daily loss amount
        """
        self.daily_loss += loss

    def reset_daily_counters(self):
        """Reset daily counters for new trading day."""
        self.daily_loss = 0
        self.daily_trades = 0

    def should_halt_trading(self, portfolio_value: float) -> tuple[bool, str]:
        """Check if trading should be halted.

        Args:
            portfolio_value: Current portfolio value

        Returns:
            Tuple of (should_halt, reason)
        """
        # Check daily loss
        if self.daily_loss > self.limits.max_daily_loss:
            return True, f"Daily loss limit exceeded ({self.daily_loss:.1%} > {self.limits.max_daily_loss:.1%})"

        # Check drawdown
        passes, drawdown = self.check_drawdown_limit(portfolio_value)
        if not passes:
            return True, f"Drawdown limit exceeded ({drawdown:.1%} > {self.limits.max_drawdown:.1%})"

        return False, "OK"

    def check_option_position_limits(
        self,
        portfolio_value: float,
        current_option_positions: List[OptionPosition],
        new_option_position: OptionPosition
    ) -> tuple[bool, str]:
        """Check if adding an options position would exceed options-specific limits.

        Args:
            portfolio_value: Total portfolio value
            current_option_positions: Current options positions
            new_option_position: New options position to add

        Returns:
            Tuple of (passes, reason)
        """
        # Calculate new totals if position is added
        new_total_notional = self.total_option_notional + new_option_position.get_notional_value()
        new_portfolio_greeks = self.portfolio_greeks + new_option_position.get_position_greeks()

        # Check max single option position
        if new_option_position.get_market_value() > portfolio_value * self.limits.max_single_option_position:
            return False, f"Single option position exceeds limit ({new_option_position.get_market_value()/portfolio_value:.1%} > {self.limits.max_single_option_position:.1%})"

        # Check max option notional
        if new_total_notional > portfolio_value * self.limits.max_option_notional:
            return False, f"Option notional exceeds limit ({new_total_notional/portfolio_value:.1%} > {self.limits.max_option_notional:.1%})"

        # Check max net delta
        if abs(new_portfolio_greeks.delta) > portfolio_value * self.limits.max_net_delta:
            return False, f"Net delta exposure exceeds limit ({abs(new_portfolio_greeks.delta)/portfolio_value:.1%} > {self.limits.max_net_delta:.1%})"

        # Check max gamma exposure
        if abs(new_portfolio_greeks.gamma) > portfolio_value * self.limits.max_gamma_exposure:
            return False, f"Gamma exposure exceeds limit ({abs(new_portfolio_greeks.gamma)/portfolio_value:.1%} > {self.limits.max_gamma_exposure:.1%})"

        # Check max vega exposure
        if abs(new_portfolio_greeks.vega) > portfolio_value * self.limits.max_vega_exposure:
            return False, f"Vega exposure exceeds limit ({abs(new_portfolio_greeks.vega)/portfolio_value:.1%} > {self.limits.max_vega_exposure:.1%})"

        return True, "OK"

    def update_option_portfolio_greeks(
        self,
        current_option_positions: List[OptionPosition],
        removed_positions: List[OptionPosition] = None,
        added_positions: List[OptionPosition] = None
    ):
        """Update portfolio Greeks based on current options positions.

        Args:
            current_option_positions: Current options positions
            removed_positions: Positions that were removed (optional)
            added_positions: Positions that were added (optional)
        """
        if removed_positions is None:
            removed_positions = []
        if added_positions is None:
            added_positions = []

        # Calculate Greeks for removed positions
        removed_greeks = PortfolioGreeks()
        for pos in removed_positions:
            removed_greeks = removed_greeks + pos.get_position_greeks()

        # Calculate Greeks for added positions
        added_greeks = PortfolioGreeks()
        for pos in added_positions:
            added_greeks = added_greeks + pos.get_position_greeks()

        # Update portfolio Greeks
        self.portfolio_greeks = self.portfolio_greeks - removed_greeks + added_greeks

        # Update total option notional
        removed_notional = sum(pos.get_notional_value() for pos in removed_positions)
        added_notional = sum(pos.get_notional_value() for pos in added_positions)
        self.total_option_notional = self.total_option_notional - removed_notional + added_notional


class PositionTracker:
    """Track positions and calculate exposure."""

    def __init__(self):
        """Initialize position tracker."""
        self.positions: dict[str, dict] = {}
        self.cash: float = 0
        self.total_exposure: float = 0
        self.total_value: float = 0

    def add_position(
        self,
        symbol: str,
        quantity: float,
        average_cost: float,
        current_price: float
    ):
        """Add or update a position.

        Args:
            symbol: Stock symbol
            quantity: Number of shares
            average_cost: Average cost per share
            current_price: Current price per share
        """
        self.positions[symbol] = {
            'quantity': quantity,
            'average_cost': average_cost,
            'current_price': current_price,
            'value': quantity * current_price
        }
        self._recalculate()

    def remove_position(self, symbol: str):
        """Remove a position.

        Args:
            symbol: Stock symbol to remove
        """
        if symbol in self.positions:
            del self.positions[symbol]
            self._recalculate()

    def update_prices(self, prices: dict[str, float]):
        """Update current prices for all positions.

        Args:
            prices: Dictionary of symbol -> price
        """
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol]['current_price'] = price
                self.positions[symbol]['value'] = (
                    self.positions[symbol]['quantity'] * price
                )
        self._recalculate()

    def _recalculate(self):
        """Recalculate totals."""
        self.total_exposure = sum(p['value'] for p in self.positions.values())
        self.total_value = self.cash + self.total_exposure

    def get_exposure(self) -> float:
        """Get total market exposure."""
        return self.total_exposure

    def get_positions(self) -> dict[str, dict]:
        """Get all positions."""
        return self.positions.copy()


class RiskManager:
    """Main risk manager that coordinates all risk checks."""

    def __init__(self, limits: RiskLimits):
        """Initialize risk manager.

        Args:
            limits: Risk limits configuration
        """
        self.limits = limits
        self.risk_checker = RiskChecker(limits)
        self.position_tracker = PositionTracker()
        self.option_positions: Dict[str, OptionPosition] = {}  # option_symbol -> OptionPosition

    def can_open_position(
        self,
        portfolio_value: float,
        symbol: str,
        position_value: float
    ) -> tuple[bool, str]:
        """Check if a new position can be opened.

        Args:
            portfolio_value: Total portfolio value
            symbol: Symbol to trade
            position_value: Value of new position

        Returns:
            Tuple of (can_open, reason)
        """
        # Check position limit
        passes, reason = self.risk_checker.check_position_limit(
            portfolio_value, self.position_tracker.get_positions(), position_value
        )

        if not passes:
            return False, reason

        return True, "OK"

    def can_open_option_position(
        self,
        portfolio_value: float,
        option_position: OptionPosition
    ) -> tuple[bool, str]:
        """Check if a new options position can be opened.

        Args:
            portfolio_value: Total portfolio value
            option_position: New options position to add

        Returns:
            Tuple of (can_open, reason)
        """
        # Check options-specific position limits
        passes, reason = self.risk_checker.check_option_position_limits(
            portfolio_value, list(self.option_positions.values()), option_position
        )

        if not passes:
            return False, reason

        # Also check regular position limits for the underlying exposure
        underlying_exposure = option_position.get_notional_value()
        passes, reason = self.risk_checker.check_position_limit(
            portfolio_value,
            {k: {'value': v.get_notional_value()} for k, v in self.option_positions.items()},
            underlying_exposure
        )

        if not passes:
            return False, reason

        return True, "OK"

    def can_trade(self, portfolio_value: float) -> tuple[bool, str]:
        """Check if trading is allowed.

        Args:
            portfolio_value: Total portfolio value

        Returns:
            Tuple of (can_trade, reason)
        """
        # Check halt conditions
        should_halt, reason = self.risk_checker.should_halt_trading(portfolio_value)

        if should_halt:
            return False, reason

        # Check daily trades limit
        passes, trades = self.risk_checker.check_daily_trades_limit()

        if not passes:
            return False, f"Daily trade limit reached ({trades} >= {self.limits.max_daily_trades})"

        return True, "OK"

    def reset_daily(self):
        """Reset daily counters."""
        self.risk_checker.reset_daily_counters()

    def record_trade(self):
        """Record a trade for daily limit tracking."""
        self.risk_checker.daily_trades += 1

    def record_daily_loss(self, loss: float):
        """Record a daily loss.

        Args:
            loss: Loss amount
        """
        self.risk_checker.update_daily_loss(loss)

    def record_position(
        self,
        symbol: str,
        quantity: float,
        average_cost: float,
        current_price: float
    ):
        """Record a new or updated position.

        Args:
            symbol: Stock symbol
            quantity: Number of shares
            average_cost: Average cost per share
            current_price: Current price per share
        """
        self.position_tracker.add_position(symbol, quantity, average_cost, current_price)

    def record_exit(self, symbol: str):
        """Record a position exit.

        Args:
            symbol: Stock symbol
        """
        self.position_tracker.remove_position(symbol)

    def record_option_position(
        self,
        option_position: OptionPosition
    ):
        """Record a new or updated options position.

        Args:
            option_position: Options position to record
        """
        self.option_positions[option_position.option_symbol] = option_position

        # Update portfolio Greeks and notional
        added_greeks = option_position.get_position_greeks()
        added_notional = option_position.get_notional_value()

        self.risk_checker.portfolio_greeks = self.risk_checker.portfolio_greeks + added_greeks
        self.risk_checker.total_option_notional = self.risk_checker.total_option_notional + added_notional

    def record_option_exit(self, option_symbol: str):
        """Record an options position exit.

        Args:
            option_symbol: Options symbol to remove
        """
        if option_symbol in self.option_positions:
            # Remove from tracking and update Greeks/notional
            removed_position = self.option_positions[option_symbol]
            removed_greeks = removed_position.get_position_greeks()
            removed_notional = removed_position.get_notional_value()

            self.risk_checker.portfolio_greeks = self.risk_checker.portfolio_greeks - removed_greeks
            self.risk_checker.total_option_notional = self.risk_checker.total_option_notional - removed_notional

            del self.option_positions[option_symbol]

    def update_option_prices(self, prices: Dict[str, float]):
        """Update current prices for all options positions.

        Args:
            prices: Dictionary of option_symbol -> price
        """
        for option_symbol, price in prices.items():
            if option_symbol in self.option_positions:
                old_position = self.option_positions[option_symbol]
                # Create updated position with new price
                updated_position = OptionPosition(
                    symbol=old_position.symbol,
                    option_symbol=old_position.option_symbol,
                    quantity=old_position.quantity,
                    strike=old_position.strike,
                    expiration=old_position.expiration,
                    option_type=old_position.option_type,
                    entry_price=old_position.entry_price,
                    current_price=price,
                    underlying_price=old_position.underlying_price,
                    delta=old_position.delta,
                    gamma=old_position.gamma,
                    theta=old_position.theta,
                    vega=old_position.vega,
                    rho=old_position.rho
                )

                # Update the position
                self.record_option_exit(option_symbol)
                self.record_option_position(updated_position)

    def get_portfolio_greeks(self) -> PortfolioGreeks:
        """Get current portfolio Greeks."""
        return self.risk_checker.portfolio_greeks

    def get_total_option_notional(self) -> float:
        """Get total option notional exposure."""
        return self.risk_checker.total_option_notional

    def get_option_positions(self) -> Dict[str, OptionPosition]:
        """Get all options positions."""
        return self.option_positions.copy()

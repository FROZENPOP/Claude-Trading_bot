"""Portfolio sizing module for volatility-adjusted position sizing."""

import pandas as pd
import numpy as np
from typing import Optional


class VolatilitySizing:
    """Calculate position size based on volatility."""

    def __init__(
        self,
        target_volatility: float = 0.15,  # 15% annualized
        trading_days_per_year: int = 252
    ):
        """Initialize volatility sizer.

        Args:
            target_volatility: Target annualized volatility
            trading_days_per_year: Number of trading days per year
        """
        self.target_volatility = target_volatility
        self.trading_days_per_year = trading_days_per_year

    def calculate_position_size(
        self,
        portfolio_value: float,
        asset_volatility: float,
        asset_price: float
    ) -> float:
        """Calculate position size based on volatility targeting.

        The formula is:
        position_size = (target_volatility / asset_volatility) * portfolio_value / asset_price

        This ensures each position contributes approximately the target volatility
        to the overall portfolio.

        Args:
            portfolio_value: Total portfolio value
            asset_volatility: Asset's annualized volatility
            asset_price: Current asset price

        Returns:
            Number of shares to buy
        """
        if asset_volatility <= 0:
            return 0

        # Calculate the dollar amount for target volatility contribution
        target_dollar_amount = (self.target_volatility / asset_volatility) * portfolio_value

        # Convert to shares
        shares = target_dollar_amount / asset_price

        return shares

    def calculate_target_volatility(
        self,
        portfolio_value: float,
        shares: float,
        asset_volatility: float
    ) -> float:
        """Calculate the volatility contribution of a position.

        Args:
            portfolio_value: Total portfolio value
            shares: Number of shares
            asset_volatility: Asset's annualized volatility

        Returns:
            Portfolio volatility contribution
        """
        dollar_amount = shares * asset_price if 'asset_price' in locals() else 0
        # This needs the price - use alternative calculation
        return (shares * asset_price / portfolio_value) * asset_volatility if portfolio_value > 0 else 0


class ConstrainedSizing:
    """Apply constraints to position sizing."""

    def __init__(
        self,
        max_position_size: float = 0.10,  # 10% of portfolio
        max_portfolio_exposure: float = 1.0,  # 100%
        min_position_size: float = 0.001,  # 0.1% of portfolio
        max_open_positions: int = 10
    ):
        """Initialize constrained sizer.

        Args:
            max_position_size: Maximum position as % of portfolio
            max_portfolio_exposure: Maximum total exposure as % of portfolio
            min_position_size: Minimum position as % of portfolio
            max_open_positions: Maximum number of open positions
        """
        self.max_position_size = max_position_size
        self.max_portfolio_exposure = max_portfolio_exposure
        self.min_position_size = min_position_size
        self.max_open_positions = max_open_positions

    def apply_position_limit(
        self,
        calculated_shares: float,
        portfolio_value: float,
        asset_price: float
    ) -> float:
        """Apply maximum position size limit.

        Args:
            calculated_shares: Calculated position size
            portfolio_value: Total portfolio value
            asset_price: Current asset price

        Returns:
            Constrained number of shares
        """
        calculated_value = calculated_shares * asset_price
        max_value = portfolio_value * self.max_position_size

        return min(calculated_shares, max_value / asset_price)

    def apply_exposure_limit(
        self,
        current_exposure: float,
        new_position_value: float,
        portfolio_value: float
    ) -> float:
        """Apply portfolio exposure limit.

        Args:
            current_exposure: Current total exposure
            new_position_value: Value of new position
            portfolio_value: Total portfolio value

        Returns:
            Constrained new position value
        """
        max_exposure = portfolio_value * self.max_portfolio_exposure

        if current_exposure + new_position_value > max_exposure:
            return max(0, max_exposure - current_exposure)

        return new_position_value

    def is_position_too_small(
        self,
        position_value: float,
        portfolio_value: float
    ) -> bool:
        """Check if position is too small to trade.

        Args:
            position_value: Value of position
            portfolio_value: Total portfolio value

        Returns:
            True if position is too small
        """
        if portfolio_value == 0:
            return True

        position_pct = position_value / portfolio_value
        return position_pct < self.min_position_size


class PositionSizer:
    """Main position sizer that combines volatility targeting with constraints."""

    def __init__(
        self,
        volatility_sizer: Optional[VolatilitySizing] = None,
        constrained_sizer: Optional[ConstrainedSizing] = None
    ):
        """Initialize position sizer.

        Args:
            volatility_sizer: Volatility-based sizer instance
            constrained_sizer: Constraint-based sizer instance
        """
        self.volatility_sizer = volatility_sizer or VolatilitySizing()
        self.constrained_sizer = constrained_sizer or ConstrainedSizing()

    def calculate_sized_position(
        self,
        portfolio_value: float,
        asset_volatility: float,
        asset_price: float,
        current_exposure: float = 0.0
    ) -> tuple[float, dict]:
        """Calculate the final position size with all constraints.

        Args:
            portfolio_value: Total portfolio value
            asset_volatility: Asset's annualized volatility
            asset_price: Current asset price
            current_exposure: Current total exposure

        Returns:
            Tuple of (shares, metadata dictionary)
        """
        # Step 1: Calculate volatility-targeted position
        shares = self.volatility_sizer.calculate_position_size(
            portfolio_value, asset_volatility, asset_price
        )

        # Step 2: Apply position size limit
        shares = self.constrained_sizer.apply_position_limit(
            shares, portfolio_value, asset_price
        )

        # Step 3: Check if position is too small
        position_value = shares * asset_price
        if self.constrained_sizer.is_position_too_small(position_value, portfolio_value):
            return 0, {'reason': 'position_too_small', 'position_value': position_value}

        # Step 4: Check exposure limit
        new_exposure = current_exposure + position_value
        if new_exposure > portfolio_value * self.constrained_sizer.max_portfolio_exposure:
            remaining_exposure = portfolio_value * self.constrained_sizer.max_portfolio_exposure - current_exposure
            shares = remaining_exposure / asset_price if asset_price > 0 else 0

        # Final check for minimum size
        final_value = shares * asset_price
        if final_value < portfolio_value * self.constrained_sizer.min_position_size:
            return 0, {'reason': 'below_minimum', 'final_value': final_value}

        return shares, {'reason': 'success', 'final_value': final_value}


def calculate_position_for_risk(
    portfolio_value: float,
    asset_volatility: float,
    asset_price: float,
    target_risk: float,
    max_position: float = 0.10
) -> float:
    """Calculate position size for a target dollar risk amount.

    Args:
        portfolio_value: Total portfolio value
        asset_volatility: Asset's annualized volatility
        asset_price: Current asset price
        target_risk: Target risk amount (e.g., $1000)
        max_position: Maximum position as % of portfolio

    Returns:
        Number of shares to buy
    """
    if asset_volatility <= 0:
        return 0

    # For a position, dollar volatility = shares * price * asset_volatility / sqrt(252)
    # (assuming independent daily returns)
    daily_vol_per_share = asset_price * asset_volatility / np.sqrt(252)

    # Shares for target daily risk
    shares = target_risk / daily_vol_per_share if daily_vol_per_share > 0 else 0

    # Apply position limit
    max_shares = (portfolio_value * max_position) / asset_price
    return min(shares, max_shares)

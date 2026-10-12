"""Main trend following strategy implementation."""

import pandas as pd
import numpy as np
from typing import Optional
import logging

from trading_bot.strategies.composite_score import CompositeTrendScore

logger = logging.getLogger(__name__)


class TrendFollowingStrategy:
    """Volatility-adjusted trend following strategy.

    This strategy:
    1. Calculates a composite trend score from multiple signals
    2. Only enters positions when score exceeds entry threshold
    3. Exits when score falls below exit threshold
    4. Uses volatility adjustment for position sizing
    """

    def __init__(
        self,
        entry_threshold: float = 0.5,
        exit_threshold: float = -0.3,
        weights: Optional[dict] = None,
        short_window: int = 20,
        medium_window: int = 50,
        long_window: int = 200,
        momentum_lookbacks: Optional[list] = None,
        volatility_window: int = 21
    ):
        """Initialize the trend following strategy.

        Args:
            entry_threshold: Minimum composite score to enter position
            exit_threshold: Maximum composite score to exit position
            weights: Signal weights for composite score
            short_window: Short MA window
            medium_window: Medium MA window
            long_window: Long MA window
            momentum_lookbacks: List of momentum lookback periods
            volatility_window: Window for volatility calculation
        """
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.short_window = short_window
        self.medium_window = medium_window
        self.long_window = long_window
        self.momentum_lookbacks = momentum_lookbacks or [21, 63, 126, 252]
        self.volatility_window = volatility_window

        self.composite_calculator = CompositeTrendScore(
            weights=weights,
            entry_threshold=entry_threshold,
            exit_threshold=exit_threshold
        )

    def calculate_all_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate all strategy indicators on the data.

        Args:
            data: DataFrame with 'adjusted_close' column

        Returns:
            DataFrame with added indicator columns
        """
        prices = data['adjusted_close']

        # Calculate MAs
        data['short_ma'] = prices.rolling(self.short_window).mean()
        data['medium_ma'] = prices.rolling(self.medium_window).mean()
        data['long_ma'] = prices.rolling(self.long_window).mean()

        # Calculate volatility
        daily_returns = prices.pct_change()
        data['realized_volatility'] = daily_returns.rolling(self.volatility_window).std() * np.sqrt(252)

        # Calculate composite score
        data['composite_score'] = self.composite_calculator.calculate_composite_score(
            prices,
            self.short_window,
            self.medium_window,
            self.long_window,
            self.momentum_lookbacks
        )

        # Generate entry/exit signals
        data['signal'] = 0
        data.loc[data['composite_score'] > self.entry_threshold, 'signal'] = 1
        data.loc[data['composite_score'] < self.exit_threshold, 'signal'] = -1

        # Track position state
        data['in_position'] = False
        data.loc[data['signal'] == 1, 'in_position'] = True

        return data

    def get_entry_signal(self, data: pd.DataFrame, day: int) -> bool:
        """Check if an entry signal should be generated.

        Args:
            data: DataFrame with calculated indicators
            day: Current day index

        Returns:
            True if entry signal should be generated
        """
        if day < self.long_window + self.volatility_window:  # Need enough data for all indicators
            return False

        # Entry signal: composite score above threshold AND not already in position
        current_score = data.iloc[day]['composite_score']
        prev_score = data.iloc[day - 1]['composite_score'] if day > 0 else None

        # Require score to cross above threshold (not just be above it)
        entry_condition = (
            current_score > self.entry_threshold and
            (prev_score is None or prev_score <= self.entry_threshold)
        )

        return entry_condition

    def get_exit_signal(self, data: pd.DataFrame, day: int) -> bool:
        """Check if an exit signal should be generated.

        Args:
            data: DataFrame with calculated indicators
            day: Current day index

        Returns:
            True if exit signal should be generated
        """
        if day < self.long_window + self.volatility_window:
            return False

        current_score = data.iloc[day]['composite_score']
        prev_score = data.iloc[day - 1]['composite_score'] if day > 0 else None

        # Exit condition: score below exit threshold
        exit_condition = (
            current_score < self.exit_threshold and
            (prev_score is None or prev_score >= self.exit_threshold)
        )

        return exit_condition

    def should_exit_long_position(self, data: pd.DataFrame, day: int) -> bool:
        """Check if a long position should be exited.

        Args:
            data: DataFrame with calculated indicators
            day: Current day index

        Returns:
            True if position should be exited
        """
        return self.get_exit_signal(data, day)

    def get_composite_score(self, data: pd.DataFrame, day: int) -> float:
        """Get the composite score for a specific day.

        Args:
            data: DataFrame with calculated indicators
            day: Day index

        Returns:
            Composite score value
        """
        return float(data.iloc[day]['composite_score'])

    def get_score_breakdown(
        self,
        prices: pd.Series
    ) -> dict[str, float]:
        """Get individual signal scores for debugging.

        Args:
            prices: Series of prices

        Returns:
            Dictionary of signal names to scores
        """
        signals = {
            'short_ma': float(self.composite_calculator.calculate_short_medium_trend(
                prices, self.short_window, self.medium_window
            ).iloc[-1]),
            'medium_ma': float(self.composite_calculator.calculate_medium_long_trend(
                prices, self.medium_window, self.long_window
            ).iloc[-1]),
            'momentum': float(self.composite_calculator.calculate_momentum_score(
                prices, self.momentum_lookbacks
            ).iloc[-1]),
            'price_relative': float(self.composite_calculator.calculate_price_relative_score(
                prices, self.long_window
            ).iloc[-1]),
            'vol_adjusted': float(self.composite_calculator.calculate_volatility_adjusted_momentum(
                prices, self.volatility_window, 63
            ).iloc[-1]),
        }

        return signals
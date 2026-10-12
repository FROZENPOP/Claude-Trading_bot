"""Composite trend score calculation module."""

import pandas as pd
import numpy as np
from typing import Optional


class CompositeTrendScore:
    """Aggregate multiple trend signals into a composite score.

    The composite score represents the strength and consistency of the trend
    across multiple measurements:
    - Short/medium MA trend
    - Medium/long MA trend
    - Price momentum (multiple lookbacks)
    - Price relative to long-term MA
    - Volatility-adjusted momentum
    """

    def __init__(
        self,
        weights: Optional[dict] = None,
        entry_threshold: float = 0.5,
        exit_threshold: float = -0.3
    ):
        """Initialize composite trend score calculator.

        Args:
            weights: Dictionary of signal weights. Defaults to:
                - short_ma: 0.25
                - medium_ma: 0.25
                - momentum: 0.25
                - price_relative: 0.15
                - vol_adjusted: 0.10
            entry_threshold: Minimum composite score to enter position
            exit_threshold: Maximum composite score to exit position
        """
        self.weights = weights or {
            'short_ma': 0.25,
            'medium_ma': 0.25,
            'momentum': 0.25,
            'price_relative': 0.15,
            'vol_adjusted': 0.10
        }
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold

        # Validate weights sum to 1
        weight_sum = sum(self.weights.values())
        if abs(weight_sum - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {weight_sum}")

    def normalize_signal_bounded(self, series: pd.Series) -> pd.Series:
        """Normalize a signal to -1 to +1 range using clipping.

        Args:
            series: Input series

        Returns:
            Normalized series in -1 to +1 range
        """
        return series.clip(-1, 1)

    def calculate_short_medium_trend(
        self,
        prices: pd.Series,
        short_window: int = 20,
        medium_window: int = 50
    ) -> pd.Series:
        """Calculate short/medium MA trend signal.

        Returns normalized score between -1 and +1.
        +1 = short MA far above medium MA (strong uptrend)
        -1 = short MA far below medium MA (strong downtrend)

        Args:
            prices: Series of prices
            short_window: Short MA window
            medium_window: Medium MA window

        Returns:
            Normalized trend score
        """
        short_ma = prices.rolling(short_window).mean()
        medium_ma = prices.rolling(medium_window).mean()

        # Percentage difference between MAs
        diff_pct = (short_ma - medium_ma) / medium_ma

        return self.normalize_signal_bounded(diff_pct)

    def calculate_medium_long_trend(
        self,
        prices: pd.Series,
        medium_window: int = 50,
        long_window: int = 200
    ) -> pd.Series:
        """Calculate medium/long MA trend signal.

        Args:
            prices: Series of prices
            medium_window: Medium MA window
            long_window: Long MA window

        Returns:
            Normalized trend score
        """
        medium_ma = prices.rolling(medium_window).mean()
        long_ma = prices.rolling(long_window).mean()

        # Percentage difference between MAs
        diff_pct = (medium_ma - long_ma) / long_ma

        return self.normalize_signal_bounded(diff_pct)

    def calculate_momentum_score(
        self,
        prices: pd.Series,
        lookbacks: Optional[list] = None
    ) -> pd.Series:
        """Calculate momentum signal across multiple lookbacks.

        Args:
            prices: Series of prices
            lookbacks: List of momentum lookback periods (default: [21, 63, 126, 252])

        Returns:
            Average normalized momentum score
        """
        lookbacks = lookbacks or [21, 63, 126, 252]

        momentum_scores = []
        for lookback in lookbacks:
            momentum = (prices / prices.shift(lookback) - 1) * 100
            momentum_scores.append(self.normalize_signal_bounded(momentum))

        # Average across all lookbacks
        if len(momentum_scores) == 1:
            return momentum_scores[0]

        return pd.concat(momentum_scores, axis=1).mean(axis=1)

    def calculate_price_relative_score(
        self,
        prices: pd.Series,
        long_ma_window: int = 200
    ) -> pd.Series:
        """Calculate price relative to long-term MA.

        Args:
            prices: Series of prices
            long_ma_window: Long MA window

        Returns:
            Normalized price relative score
        """
        long_ma = prices.rolling(long_ma_window).mean()
        relative = (prices / long_ma) - 1

        return self.normalize_signal_bounded(relative)

    def calculate_volatility_adjusted_momentum(
        self,
        prices: pd.Series,
        volatility_window: int = 21,
        momentum_lookback: int = 63
    ) -> pd.Series:
        """Calculate volatility-adjusted momentum (Sharpe-like ratio).

        Volatility-adjusted momentum = momentum / realized_volatility

        Args:
            prices: Series of prices
            volatility_window: Window for volatility calculation
            momentum_lookback: Lookback for momentum

        Returns:
            Volatility-adjusted momentum score
        """
        # Calculate momentum
        momentum = prices.pct_change(momentum_lookback) * 100

        # Calculate realized volatility (annualized)
        daily_returns = prices.pct_change()
        volatility = daily_returns.rolling(volatility_window).std() * np.sqrt(252)

        # Avoid division by zero
        with np.errstate(divide='ignore', invalid='ignore'):
            vol_adj = np.where(volatility > 0.001, momentum / volatility, 0)

        return self.normalize_signal_bounded(pd.Series(vol_adj, index=prices.index))

    def calculate_composite_score(
        self,
        prices: pd.Series,
        short_window: int = 20,
        medium_window: int = 50,
        long_window: int = 200,
        momentum_lookbacks: Optional[list] = None,
        override_weights: Optional[dict] = None
    ) -> pd.Series:
        """Calculate the full composite trend score.

        The composite score is a weighted average of:
        1. Short/medium MA trend (25%)
        2. Medium/long MA trend (25%)
        3. Momentum across lookbacks (25%)
        4. Price relative to long MA (15%)
        5. Volatility-adjusted momentum (10%)

        Args:
            prices: Series of prices
            short_window: Short MA window
            medium_window: Medium MA window
            long_window: Long MA window
            momentum_lookbacks: List of momentum lookback periods
            override_weights: Optional weight overrides

        Returns:
            Series of composite trend scores
        """
        weights = override_weights or self.weights

        # Calculate individual signals
        signals = {
            'short_ma': self.calculate_short_medium_trend(prices, short_window, medium_window),
            'medium_ma': self.calculate_medium_long_trend(prices, medium_window, long_window),
            'momentum': self.calculate_momentum_score(prices, momentum_lookbacks),
            'price_relative': self.calculate_price_relative_score(prices, long_window),
            'vol_adjusted': self.calculate_volatility_adjusted_momentum(prices, 21, 63)
        }

        # Weighted average
        composite = pd.Series(0, index=prices.index)
        for signal_name, signal_data in signals.items():
            composite += weights[signal_name] * signal_data

        return composite

    def generate_trading_signals(
        self,
        composite_score: pd.Series
    ) -> pd.Series:
        """Generate trading signals from composite score.

        Args:
            composite_score: Series of composite trend scores

        Returns:
            Series of trading signals: 1 (enter), 0 (hold), -1 (exit)
        """
        signals = pd.Series(0, index=composite_score.index)

        # Enter position when score exceeds entry threshold
        signals[composite_score > self.entry_threshold] = 1

        # Exit position when score falls below exit threshold
        signals[composite_score < self.exit_threshold] = -1

        return signals
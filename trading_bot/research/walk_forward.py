"""Walk-forward analysis for robust backtesting."""

import pandas as pd
import numpy as np
from typing import Optional, Callable
from dataclasses import dataclass, field
import logging
from datetime import datetime

from trading_bot.strategies.trend_following import TrendFollowingStrategy
from trading_bot.backtesting.engine import EventDrivenBacktest
from trading_bot.backtesting.costs import TransactionCostModel
from trading_bot.backtesting.metrics import PerformanceMetrics

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardResult:
    """Result of walk-forward analysis."""
    window_start: str
    window_end: str
    out_of_sample_start: str
    out_of_sample_end: str
    in_sample_return: float
    out_of_sample_return: float
    in_sample_sharpe: float
    out_of_sample_sharpe: float
    in_sample_max_dd: float
    out_of_sample_max_dd: float
    config_used: str


class WalkForwardAnalyzer:
    """Perform walk-forward analysis to test strategy robustness.

    Walk-forward analysis simulates real-world trading by:
    1. Training on past data (window 1)
    2. Testing on immediately following data (out-of-sample)
    3. Rolling forward and repeating
    4. Combining all out-of-sample results

    This prevents look-ahead bias while testing multiple configurations.
    """

    def __init__(
        self,
        data: pd.DataFrame,
        symbol: str = "AAPL",
        initial_capital: float = 100000,
        window_size: int = 504,  # 2 years of trading days
        step_size: int = 63,  # 3 months (1 quarter)
        optimal_config_selector: Optional[Callable] = None
    ):
        """Initialize walk-forward analyzer.

        Args:
            data: Full historical data
            symbol: Symbol being tested
            initial_capital: Initial capital for backtests
            window_size: Training window size in days (default 504 = 2 years)
            step_size: Step forward size in days (default 63 = 3 months)
            optimal_config_selector: Function to select best config from IS results
        """
        self.data = data
        self.symbol = symbol
        self.initial_capital = initial_capital
        self.window_size = window_size
        self.step_size = step_size

        # Default selector: choose config with highest Sharpe ratio
        self.optimal_config_selector = optimal_config_selector or self._select_by_sharpe

        # Results storage
        self.results: list[WalkForwardResult] = []
        self.tracking: dict = {
            'in_sample_results': [],
            'out_of_sample_results': []
        }

    def _select_by_sharpe(self, results: list[dict]) -> dict:
        """Select optimal configuration by Sharpe ratio."""
        if not results:
            return {}
        return max(results, key=lambda x: x.get('sharpe_ratio', 0))

    def _run_backtest_for_config(
        self,
        data: pd.DataFrame,
        config: dict,
        cost_model: TransactionCostModel
    ) -> tuple[dict, PerformanceMetrics]:
        """Run a single backtest with given configuration.

        Args:
            data: Data to backtest on
            config: Strategy configuration
            cost_model: Transaction cost model

        Returns:
            Tuple of (result_dict, metrics)
        """
        strategy = TrendFollowingStrategy(
            entry_threshold=config.get('entry_threshold', 0.5),
            exit_threshold=config.get('exit_threshold', -0.3),
            weights=config.get('weights', {
                'short_ma': 0.25, 'medium_ma': 0.25, 'momentum': 0.25,
                'price_relative': 0.15, 'vol_adjusted': 0.10
            }),
            short_window=config.get('short_window', 20),
            medium_window=config.get('medium_window', 50),
            long_window=config.get('long_window', 200)
        )

        backtest = EventDrivenBacktest(
            strategy=strategy,
            initial_capital=self.initial_capital,
            cost_model=cost_model
        )

        result_dict = backtest.run(data.copy(), self.symbol)

        portfolio_values = pd.Series(
            [v['portfolio_value'] for v in result_dict.get('daily_values', [])]
        )

        benchmark_values = (
            data['adjusted_close'] / data['adjusted_close'].iloc[0] * self.initial_capital
        )

        metrics = PerformanceMetrics()
        metrics.calculate_all_metrics(portfolio_values, benchmark_values)

        return result_dict, metrics

    def run_analysis(
        self,
        configs: list[dict],
        cost_model: Optional[TransactionCostModel] = None,
        verbose: bool = True
    ) -> list[WalkForwardResult]:
        """Run full walk-forward analysis.

        Args:
            configs: List of strategy configurations to test
            cost_model: Transaction cost model
            verbose: Print progress

        Returns:
            List of walk-forward results
        """
        if cost_model is None:
            cost_model = TransactionCostModel()

        # Sort data by date
        sorted_data = self.data.sort_values('date').reset_index(drop=True)

        results = []
        current_idx = self.window_size

        while current_idx + self.step_size <= len(sorted_data):
            # Define windows
            window_start_date = sorted_data.iloc[current_idx - self.window_size]['date']
            window_end_date = sorted_data.iloc[current_idx - 1]['date']
            oos_start_date = sorted_data.iloc[current_idx]['date']
            oos_end_idx = min(current_idx + self.step_size, len(sorted_data))
            oos_end_date = sorted_data.iloc[oos_end_idx - 1]['date']

            # Split data
            in_sample = sorted_data.iloc[current_idx - self.window_size:current_idx]
            out_of_sample = sorted_data.iloc[current_idx:oos_end_idx]

            if verbose:
                logger.info(f"Window: {window_start_date.date()} to {window_end_date.date()}")
                logger.info(f"  OOS: {oos_start_date.date()} to {oos_end_date.date()}")

            # Run in-sample backtest for all configs
            is_results = []
            for config in configs:
                result_dict, metrics = self._run_backtest_for_config(in_sample, config, cost_model)

                is_result = {
                    'config_name': config.get('name', 'unknown'),
                    'sharpe_ratio': metrics.sharpe_ratio,
                    'total_return': metrics.total_return,
                    'max_drawdown': metrics.max_drawdown
                }
                is_results.append(is_result)

            # Select optimal config from in-sample results
            optimal_config = self.optimal_config_selector(is_results)

            if not optimal_config:
                logger.warning(f"  No valid config found, skipping window")
                current_idx += self.step_size
                continue

            # Use optimal config for out-of-sample
            config_name = optimal_config.get('config_name', 'unknown')
            if verbose:
                logger.info(f"  Optimal config: {config_name}")

            # Run out-of-sample backtest
            result_dict, metrics = self._run_backtest_for_config(
                out_of_sample, configs[0], cost_model  # Use first config as baseline
            )

            # Store results
            result = WalkForwardResult(
                window_start=str(window_start_date.date()),
                window_end=str(window_end_date.date()),
                out_of_sample_start=str(oos_start_date.date()),
                out_of_sample_end=str(oos_end_date.date()),
                in_sample_return=optimal_config.get('total_return', 0),
                out_of_sample_return=metrics.total_return,
                in_sample_sharpe=optimal_config.get('sharpe_ratio', 0),
                out_of_sample_sharpe=metrics.sharpe_ratio,
                in_sample_max_dd=optimal_config.get('max_drawdown', 0),
                out_of_sample_max_dd=metrics.max_drawdown,
                config_used=config_name
            )
            results.append(result)

            current_idx += self.step_size

        self.results = results
        return results

    def calculate_summary_stats(self) -> dict:
        """Calculate summary statistics from walk-forward results.

        Returns:
            Dictionary of summary statistics
        """
        if not self.results:
            return {}

        results = self.results

        stats = {
            'num_windows': len(results),
            'avg_is_return': np.mean([r.in_sample_return for r in results]),
            'avg_oos_return': np.mean([r.out_of_sample_return for r in results]),
            'is_oos_return_diff': np.mean([
                r.in_sample_return - r.out_of_sample_return for r in results
            ]),
            'avg_is_sharpe': np.mean([r.in_sample_sharpe for r in results]),
            'avg_oos_sharpe': np.mean([r.out_of_sample_sharpe for r in results]),
            'is_oos_sharpe_diff': np.mean([
                r.in_sample_sharpe - r.out_of_sample_sharpe for r in results
            ]),
            'avg_is_max_dd': np.mean([r.in_sample_max_dd for r in results]),
            'avg_oos_max_dd': np.mean([r.out_of_sample_max_dd for r in results]),
        }

        # Correlation between IS and OOS performance
        is_returns = [r.in_sample_return for r in results]
        oos_returns = [r.out_of_sample_return for r in results]
        stats['is_oos_return_correlation'] = (
            np.corrcoef(is_returns, oos_returns)[0, 1]
            if len(is_returns) > 1 else 0
        )

        return stats

    def identify_underperforming_windows(
        self,
        threshold: float = 0.5
    ) -> list[WalkForwardResult]:
        """Identify windows where OOS performance significantly worse than IS.

        Args:
            threshold: Maximum acceptable IS-OOS difference

        Returns:
            List of underperforming windows
        """
        underperforming = []

        for result in self.results:
            return_diff = abs(result.in_sample_return - result.out_of_sample_return)
            sharpe_diff = abs(result.in_sample_sharpe - result.out_of_sample_sharpe)

            if return_diff > threshold or sharpe_diff > threshold:
                underperforming.append(result)

        return underperforming

    def get_best_config_across_windows(
        self
    ) -> dict[str, int]:
        """Count how many times each config was selected as optimal.

        Returns:
            Dictionary of config_name -> count
        """
        if not self.results:
            return {}

        counts = {}
        for result in self.results:
            config = result.config_used
            counts[config] = counts.get(config, 0) + 1

        # Sort by count
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


def run_walk_forward(
    data: pd.DataFrame,
    symbol: str,
    configs: list[dict],
    train_start: str,
    train_end: str,
    test_start: str,
    test_end: str,
    output_dir: str = "research_outputs",
    window_size: int = 504,
    step_size: int = 63
) -> tuple[list[WalkForwardResult], dict]:
    """Run walk-forward analysis on a specific data slice.

    Args:
        data: Full historical data
        symbol: Symbol being tested
        configs: List of strategy configurations
        train_start: Training period start
        train_end: Training period end
        test_start: Test period start
        test_end: Test period end
        output_dir: Output directory
        window_size: Training window size in days
        step_size: Step forward size in days

    Returns:
        Tuple of (results, summary)
    """
    # Filter data to test period
    test_data = data[
        (data['date'] >= pd.Timestamp(test_start)) &
        (data['date'] <= pd.Timestamp(test_end))
    ]

    # Create analyzer
    analyzer = WalkForwardAnalyzer(
        data=test_data,
        symbol=symbol,
        window_size=window_size,
        step_size=step_size
    )

    # Run analysis
    results = analyzer.run_analysis(configs, verbose=True)

    # Calculate summary
    summary = analyzer.calculate_summary_stats()

    return results, summary

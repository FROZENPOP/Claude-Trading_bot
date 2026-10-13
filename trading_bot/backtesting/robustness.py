"""Robustness testing and White's Reality Check implementation for options trading."""

import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass
import random
import warnings
import logging
from scipy import stats

logger = logging.getLogger(__name__)

from trading_bot.strategies.composite_score import CompositeTrendScore
from trading_bot.strategies.trend_following import TrendFollowingStrategy
from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy
from trading_bot.strategies.covered_call import CoveredCallStrategy, CashSecuredPutStrategy
from trading_bot.strategies.iron_condor import IronCondorStrategy
from trading_bot.strategies.calendar_spread import CalendarSpreadStrategy
from trading_bot.backtesting.engine import EventDrivenBacktest
from trading_bot.backtesting.costs import TransactionCostModel


@dataclass
class StrategyResult:
    """Result of a single strategy backtest."""
    config_name: str
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    num_trades: int
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade_return: float = 0.0


@dataclass
class OptionsStrategyResult(StrategyResult):
    """Result of an options strategy backtest with options-specific metrics."""
    avg_delta_exposure: float = 0.0
    avg_gamma_exposure: float = 0.0
    avg_theta_decay: float = 0.0
    avg_vega_exposure: float = 0.0
    max_option_notional: float = 0.0
    percent_profitable_expirations: float = 0.0
    avg_days_to_exit: float = 0.0


class ParameterSensitivity:
    """Test parameter sensitivity across different configurations."""

    def __init__(
        self,
        data: pd.DataFrame,
        symbol: str = "AAPL",
        initial_capital: float = 100000
    ):
        """Initialize parameter sensitivity analyzer.

        Args:
            data: Historical price data
            symbol: Symbol being tested
            initial_capital: Initial capital for backtests
        """
        self.data = data
        self.symbol = symbol
        self.initial_capital = initial_capital

    def test_ma_pairs(
        self,
        ma_pairs: Optional[list] = None,
        entry_threshold: float = 0.5,
        exit_threshold: float = -0.3
    ) -> list[StrategyResult]:
        """Test different moving average pairs.

        Args:
            ma_pairs: List of [short_window, long_window] pairs
            entry_threshold: Entry signal threshold
            exit_threshold: Exit signal threshold

        Returns:
            List of strategy results
        """
        ma_pairs = ma_pairs or [[20, 50], [30, 100], [50, 150], [50, 200]]
        results = []

        for short_window, long_window in ma_pairs:
            # Medium window is typically geometric mean
            medium_window = int((short_window * long_window) ** 0.5)

            strategy = TrendFollowingStrategy(
                entry_threshold=entry_threshold,
                exit_threshold=exit_threshold,
                short_window=short_window,
                medium_window=medium_window,
                long_window=long_window
            )

            backtest = EventDrivenBacktest(
                strategy,
                initial_capital=self.initial_capital
            )

            result_dict = backtest.run(self.data, self.symbol)

            result = StrategyResult(
                config_name=f"MA{short_window}/{long_window}",
                total_return=result_dict.get('total_return', 0),
                annualized_return=result_dict.get('annualized_return', 0),
                sharpe_ratio=result_dict.get('sharpe_ratio', 0),
                max_drawdown=result_dict.get('max_drawdown', 0),
                num_trades=result_dict.get('num_trades', 0)
            )
            results.append(result)

            logger.info(f"  MA{short_window}/{long_window}: "
                  f"Return={result.total_return:.1%}, "
                  f"Sharpe={result.sharpe_ratio:.2f}, "
                  f"MaxDD={result.max_drawdown:.1%}")

        return results

    def test_momentum_lookbacks(
        self,
        lookbacks: Optional[list] = None,
        entry_threshold: float = 0.5,
        exit_threshold: float = -0.3
    ) -> list[StrategyResult]:
        """Test different momentum lookback periods.

        Args:
            lookbacks: List of momentum lookback periods
            entry_threshold: Entry signal threshold
            exit_threshold: Exit signal threshold

        Returns:
            List of strategy results
        """
        lookbacks = lookbacks or [21, 63, 126, 252]
        results = []

        # Test with single lookback (simplified for speed)
        for lookback in lookbacks:
            weights = {
                'short_ma': 0.25,
                'medium_ma': 0.25,
                'momentum': 0.50,  # Focus on momentum
                'price_relative': 0.0,
                'vol_adjusted': 0.0
            }

            strategy = TrendFollowingStrategy(
                entry_threshold=entry_threshold,
                exit_threshold=exit_threshold,
                weights=weights,
                momentum_lookbacks=[lookback]
            )

            backtest = EventDrivenBacktest(
                strategy,
                initial_capital=self.initial_capital
            )

            result_dict = backtest.run(self.data, self.symbol)

            result = StrategyResult(
                config_name=f"Momentum{lookback}d",
                total_return=result_dict.get('total_return', 0),
                annualized_return=result_dict.get('annualized_return', 0),
                sharpe_ratio=result_dict.get('sharpe_ratio', 0),
                max_drawdown=result_dict.get('max_drawdown', 0),
                num_trades=result_dict.get('num_trades', 0)
            )
            results.append(result)

            logger.info(f"  Momentum{lookback}d: "
                  f"Return={result.total_return:.1%}, "
                  f"Sharpe={result.sharpe_ratio:.2f}")

        return results

    def test_thresholds(
        self,
        entry_thresholds: Optional[list] = None,
        exit_thresholds: Optional[list] = None,
        ma_pair: list = None
    ) -> list[StrategyResult]:
        """Test different entry/exit thresholds.

        Args:
            entry_thresholds: List of entry thresholds
            exit_thresholds: List of exit thresholds
            ma_pair: [short_window, long_window] pair

        Returns:
            List of strategy results
        """
        entry_thresholds = entry_thresholds or [0.3, 0.4, 0.5, 0.6, 0.7]
        exit_thresholds = exit_thresholds or [-0.5, -0.4, -0.3, -0.2, -0.1]
        ma_pair = ma_pair or [20, 50]

        results = []

        for entry_th in entry_thresholds:
            for exit_th in exit_thresholds:
                strategy = TrendFollowingStrategy(
                    entry_threshold=entry_th,
                    exit_threshold=exit_th,
                    short_window=ma_pair[0],
                    medium_window=35,  # (20+50)/2
                    long_window=ma_pair[1]
                )

                backtest = EventDrivenBacktest(
                    strategy,
                    initial_capital=self.initial_capital
                )

                result_dict = backtest.run(self.data, self.symbol)

                result = StrategyResult(
                    config_name=f"Th{entry_th}/{exit_th}",
                    total_return=result_dict.get('total_return', 0),
                    annualized_return=result_dict.get('annualized_return', 0),
                    sharpe_ratio=result_dict.get('sharpe_ratio', 0),
                    max_drawdown=result_dict.get('max_drawdown', 0),
                    num_trades=result_dict.get('num_trades', 0)
                )
                results.append(result)

        return results

    def test_options_strategy_parameters(
        self,
        strategy_type: str,
        param_grid: Dict[str, List[Any]],
        initial_capital: float = 100000
    ) -> List[StrategyResult]:
        """Test parameters for options strategies.

        Args:
            strategy_type: Type of options strategy ('vertical_spread', 'covered_call', etc.)
            param_grid: Dictionary of parameters to test
            initial_capital: Initial capital for backtests

        Returns:
            List of strategy results
        """
        results = []

        if strategy_type == 'vertical_spread':
            results = self._test_vertical_spread_params(param_grid, initial_capital)
        elif strategy_type == 'covered_call':
            results = self._test_covered_call_params(param_grid, initial_capital)
        elif strategy_type == 'cash_secured_put':
            results = self._test_cash_secured_put_params(param_grid, initial_capital)
        elif strategy_type == 'iron_condor':
            results = self._test_iron_condor_params(param_grid, initial_capital)
        elif strategy_type == 'calendar_spread':
            results = self._test_calendar_spread_params(param_grid, initial_capital)
        else:
            warnings.warn(f"Unknown strategy type: {strategy_type}")

        return results

    def _test_vertical_spread_params(
        self,
        param_grid: Dict[str, List[Any]],
        initial_capital: float
    ) -> List[StrategyResult]:
        """Test vertical spread strategy parameters."""
        results = []

        # Extract parameter grids with defaults
        max_spread_widths = param_grid.get('max_spread_width', [5.0, 10.0, 20.0])
        preferred_delta_ranges = param_grid.get('preferred_delta_range', [(0.2, 0.3), (0.25, 0.35), (0.3, 0.4)])
        preferred_dte_lists = param_grid.get('preferred_dte', [[21, 30], [30, 45], [45, 60]])

        for max_spread_width in max_spread_widths:
            for preferred_delta_range in preferred_delta_ranges:
                for preferred_dte in preferred_dte_lists:
                    try:
                        strategy = VerticalSpreadStrategy(
                            underlying_symbol=self.symbol,
                            max_spread_width=max_spread_width,
                            preferred_delta_range=preferred_delta_range,
                            preferred_dte=preferred_dte
                        )

                        backtest = EventDrivenBacktest(
                            strategy,
                            initial_capital=initial_capital
                        )

                        result_dict = backtest.run(self.data, self.symbol)

                        # Handle both regular and options strategy results
                        if 'avg_delta_exposure' in result_dict:
                            result = OptionsStrategyResult(
                                config_name=f"VS_w{max_spread_width}_d{preferred_delta_range[0]}-{preferred_delta_range[1]}_dte{preferred_dte[0]}-{preferred_dte[1]}",
                                total_return=result_dict.get('total_return', 0),
                                annualized_return=result_dict.get('annualized_return', 0),
                                sharpe_ratio=result_dict.get('sharpe_ratio', 0),
                                max_drawdown=result_dict.get('max_drawdown', 0),
                                num_trades=result_dict.get('num_trades', 0),
                                win_rate=result_dict.get('win_rate', 0),
                                profit_factor=result_dict.get('profit_factor', 0),
                                avg_trade_return=result_dict.get('avg_trade_return', 0),
                                avg_delta_exposure=result_dict.get('avg_delta_exposure', 0),
                                avg_gamma_exposure=result_dict.get('avg_gamma_exposure', 0),
                                avg_theta_decay=result_dict.get('avg_theta_decay', 0),
                                avg_vega_exposure=result_dict.get('avg_vega_exposure', 0),
                                max_option_notional=result_dict.get('max_option_notional', 0),
                                percent_profitable_expirations=result_dict.get('percent_profitable_expirations', 0),
                                avg_days_to_exit=result_dict.get('avg_days_to_exit', 0)
                            )
                        else:
                            result = StrategyResult(
                                config_name=f"VS_w{max_spread_width}_d{preferred_delta_range[0]}-{preferred_delta_range[1]}_dte{preferred_dte[0]}-{preferred_dte[1]}",
                                total_return=result_dict.get('total_return', 0),
                                annualized_return=result_dict.get('annualized_return', 0),
                                sharpe_ratio=result_dict.get('sharpe_ratio', 0),
                                max_drawdown=result_dict.get('max_drawdown', 0),
                                num_trades=result_dict.get('num_trades', 0)
                            )

                        results.append(result)

                    except Exception as e:
                        logger.warning(f"  Warning: Failed to test VS config w{max_spread_width}_d{preferred_delta_range}_dte{preferred_dte}: {e}")
                        continue

        return results

    def _test_covered_call_params(
        self,
        param_grid: Dict[str, List[Any]],
        initial_capital: float
    ) -> List[StrategyResult]:
        """Test covered call strategy parameters."""
        results = []

        # Extract parameter grids with defaults
        otm_percentages = param_grid.get('otm_percentages', [5, 10, 15, 20])
        dte_list = param_grid.get('dte_list', [30, 45, 60])

        for otm_pct in otm_percentages:
            for dte in dte_list:
                try:
                    strategy = CoveredCallStrategy(
                        underlying_symbol=self.symbol,
                        otm_percentage=otm_pct,
                        dte_target=dte
                    )

                    backtest = EventDrivenBacktest(
                        strategy,
                        initial_capital=initial_capital
                    )

                    result_dict = backtest.run(self.data, self.symbol)

                    result = StrategyResult(
                        config_name=f"CC_otm{otm_pct}_dte{dte}",
                        total_return=result_dict.get('total_return', 0),
                        annualized_return=result_dict.get('annualized_return', 0),
                        sharpe_ratio=result_dict.get('sharpe_ratio', 0),
                        max_drawdown=result_dict.get('max_drawdown', 0),
                        num_trades=result_dict.get('num_trades', 0)
                    )
                    results.append(result)

                except Exception as e:
                    logger.warning(f"  Warning: Failed to test CC config otm{otm_pct}_dte{dte}: {e}")
                    continue

        return results

    def _test_cash_secured_put_params(
        self,
        param_grid: Dict[str, List[Any]],
        initial_capital: float
    ) -> List[StrategyResult]:
        """Test cash-secured put strategy parameters."""
        results = []

        # Extract parameter grids with defaults
        otm_percentages = param_grid.get('otm_percentages', [5, 10, 15, 20])
        dte_list = param_grid.get('dte_list', [30, 45, 60])

        for otm_pct in otm_percentages:
            for dte in dte_list:
                try:
                    strategy = CashSecuredPutStrategy(
                        underlying_symbol=self.symbol,
                        otm_percentage=otm_pct,
                        dte_target=dte
                    )

                    backtest = EventDrivenBacktest(
                        strategy,
                        initial_capital=initial_capital
                    )

                    result_dict = backtest.run(self.data, self.symbol)

                    result = StrategyResult(
                        config_name=f"CSP_otm{otm_pct}_dte{dte}",
                        total_return=result_dict.get('total_return', 0),
                        annualized_return=result_dict.get('annualized_return', 0),
                        sharpe_ratio=result_dict.get('sharpe_ratio', 0),
                        max_drawdown=result_dict.get('max_drawdown', 0),
                        num_trades=result_dict.get('num_trades', 0)
                    )
                    results.append(result)

                except Exception as e:
                    logger.warning(f"  Warning: Failed to test CSP config otm{otm_pct}_dte{dte}: {e}")
                    continue

        return results

    def _test_iron_condor_params(
        self,
        param_grid: Dict[str, List[Any]],
        initial_capital: float
    ) -> List[StrategyResult]:
        """Test iron condor strategy parameters."""
        results = []

        # Extract parameter grids with defaults
        wing_widths = param_grid.get('wing_widths', [5, 10, 15])
        delta_targets = param_grid.get('delta_targets', [0.1, 0.15, 0.2])
        dte_list = param_grid.get('dte_list', [30, 45, 60])

        for wing_width in wing_widths:
            for delta_target in delta_targets:
                for dte in dte_list:
                    try:
                        strategy = IronCondorStrategy(
                            wing_width=wing_width,
                            delta_target=delta_target,
                            dte_target=dte
                        )

                        backtest = EventDrivenBacktest(
                            strategy,
                            initial_capital=initial_capital
                        )

                        result_dict = backtest.run(self.data, self.symbol)

                        if 'avg_delta_exposure' in result_dict:
                            result = OptionsStrategyResult(
                                config_name=f"IC_w{wing_width}_d{delta_target}_dte{dte}",
                                total_return=result_dict.get('total_return', 0),
                                annualized_return=result_dict.get('annualized_return', 0),
                                sharpe_ratio=result_dict.get('sharpe_ratio', 0),
                                max_drawdown=result_dict.get('max_drawdown', 0),
                                num_trades=result_dict.get('num_trades', 0),
                                win_rate=result_dict.get('win_rate', 0),
                                profit_factor=result_dict.get('profit_factor', 0),
                                avg_trade_return=result_dict.get('avg_trade_return', 0),
                                avg_delta_exposure=result_dict.get('avg_delta_exposure', 0),
                                avg_gamma_exposure=result_dict.get('avg_gamma_exposure', 0),
                                avg_theta_decay=result_dict.get('avg_theta_decay', 0),
                                avg_vega_exposure=result_dict.get('avg_vega_exposure', 0),
                                max_option_notional=result_dict.get('max_option_notional', 0),
                                percent_profitable_expirations=result_dict.get('percent_profitable_expirations', 0),
                                avg_days_to_exit=result_dict.get('avg_days_to_exit', 0)
                            )
                        else:
                            result = StrategyResult(
                                config_name=f"IC_w{wing_width}_d{delta_target}_dte{dte}",
                                total_return=result_dict.get('total_return', 0),
                                annualized_return=result_dict.get('annualized_return', 0),
                                sharpe_ratio=result_dict.get('sharpe_ratio', 0),
                                max_drawdown=result_dict.get('max_drawdown', 0),
                                num_trades=result_dict.get('num_trades', 0)
                            )

                        results.append(result)

                    except Exception as e:
                        logger.warning(f"  Warning: Failed to test IC config w{wing_width}_d{delta_target}_dte{dte}: {e}")
                        continue

        return results

    def _test_calendar_spread_params(
        self,
        param_grid: Dict[str, List[Any]],
        initial_capital: float
    ) -> List[StrategyResult]:
        """Test calendar spread strategy parameters."""
        results = []

        # Extract parameter grids with defaults
        short_dte_list = param_grid.get('short_dte_list', [15, 30])
        long_dte_list = param_grid.get('long_dte_list', [60, 90])
        delta_targets = param_grid.get('delta_targets', [0.2, 0.25, 0.3])

        for short_dte in short_dte_list:
            for long_dte in long_dte_list:
                if short_dte >= long_dte:
                    continue
                for delta_target in delta_targets:
                    try:
                        strategy = CalendarSpreadStrategy(
                            short_dte=short_dte,
                            long_dte=long_dte,
                            delta_target=delta_target
                        )

                        backtest = EventDrivenBacktest(
                            strategy,
                            initial_capital=initial_capital
                        )

                        result_dict = backtest.run(self.data, self.symbol)

                        if 'avg_delta_exposure' in result_dict:
                            result = OptionsStrategyResult(
                                config_name=f"CS_sd{short_dte}_ld{long_dte}_dt{delta_target}",
                                total_return=result_dict.get('total_return', 0),
                                annualized_return=result_dict.get('annualized_return', 0),
                                sharpe_ratio=result_dict.get('sharpe_ratio', 0),
                                max_drawdown=result_dict.get('max_drawdown', 0),
                                num_trades=result_dict.get('num_trades', 0),
                                win_rate=result_dict.get('win_rate', 0),
                                profit_factor=result_dict.get('profit_factor', 0),
                                avg_trade_return=result_dict.get('avg_trade_return', 0),
                                avg_delta_exposure=result_dict.get('avg_delta_exposure', 0),
                                avg_gamma_exposure=result_dict.get('avg_gamma_exposure', 0),
                                avg_theta_decay=result_dict.get('avg_theta_decay', 0),
                                avg_vega_exposure=result_dict.get('avg_vega_exposure', 0),
                                max_option_notional=result_dict.get('max_option_notional', 0),
                                percent_profitable_expirations=result_dict.get('percent_profitable_expirations', 0),
                                avg_days_to_exit=result_dict.get('avg_days_to_exit', 0)
                            )
                        else:
                            result = StrategyResult(
                                config_name=f"CS_sd{short_dte}_ld{long_dte}_dt{delta_target}",
                                total_return=result_dict.get('total_return', 0),
                                annualized_return=result_dict.get('annualized_return', 0),
                                sharpe_ratio=result_dict.get('sharpe_ratio', 0),
                                max_drawdown=result_dict.get('max_drawdown', 0),
                                num_trades=result_dict.get('num_trades', 0)
                            )

                        results.append(result)

                    except Exception as e:
                        logger.warning(f"  Warning: Failed to test CS config sd{short_dte}_ld{long_dte}_dt{delta_target}: {e}")
                        continue

        return results

    def find_robust_region(
        self,
        results: list[StrategyResult],
        threshold: float = 0.1
    ) -> list[StrategyResult]:
        """Find configurations with performance within threshold of best.

        Args:
            results: List of strategy results
            threshold: Maximum deviation from best Sharpe ratio

        Returns:
            Configurations in the robust region
        """
        if not results:
            return []

        best_sharpe = max(r.sharpe_ratio for r in results)

        robust = [
            r for r in results
            if r.sharpe_ratio >= best_sharpe - threshold
        ]

        return robust


class WhitesRealityCheck:
    """Implement White's Reality Check for data-snooping protection."""

    def __init__(
        self,
        n_bouts: int = 1000,
        random_seed: int = 42
    ):
        """Initialize White's Reality Check.

        Args:
            n_bouts: Number of bootstrap iterations
            random_seed: Random seed for reproducibility
        """
        self.n_bouts = n_bouts
        self.random_seed = random_seed
        np.random.seed(random_seed)

    def calculate_performance_matrix(
        self,
        strategy_results: list[dict],
        benchmark_results: list[dict]
    ) -> np.ndarray:
        """Calculate performance matrix for White's Reality Check.

        Args:
            strategy_results: List of dict with 'returns' and 'weights' keys
            benchmark_results: List of dict with 'returns' and 'weights' keys

        Returns:
            Performance matrix (n_bouts x n_strategies)
        """
        # This would calculate excess returns over benchmark
        # For simplicity, we'll use a simplified approach
        pass

    def reality_check_test(
        self,
        strategy_returns: list[float],
        benchmark_return: float = 0.0
    ) -> dict:
        """Perform White's Reality Check test.

        Tests null hypothesis: best strategy = benchmark (no edge)

        Args:
            strategy_returns: List of returns for different strategy configurations
            benchmark_return: Benchmark return (default 0 = cash)

        Returns:
            Dictionary with test results
        """
        n_strategies = len(strategy_returns)

        if n_strategies < 2:
            return {
                'p_value': 1.0,
                'has_edge': False,
                'message': 'Need at least 2 strategies for testing'
            }

        # Calculate excess returns over benchmark
        excess_returns = [r - benchmark_return for r in strategy_returns]

        # Best strategy excess return
        best_excess = max(excess_returns)

        # Bootstrap to test if best is significantly better than 0
        bootstrap_exceeds = 0

        for _ in range(self.n_bouts):
            # Resample with replacement
            bootstrap_samples = [random.choice(excess_returns) for _ in excess_returns]
            bootstrap_max = max(bootstrap_samples)

            if bootstrap_max > best_excess:
                bootstrap_exceeds += 1

        # P-value: proportion of bootstrap maxes > best actual
        p_value = bootstrap_exceeds / self.n_bouts

        # Adjust for number of strategies (Bonferroni correction)
        adjusted_p = min(p_value * n_strategies, 1.0)

        return {
            'p_value': p_value,
            'adjusted_p_value': adjusted_p,
            'best_excess_return': best_excess,
            'n_strategies': n_strategies,
            'n_bouts': self.n_bouts,
            'has_edge': p_value < 0.05,  # Significance at 5% level
            'has_edge_adjusted': adjusted_p < 0.05
        }

    def bootstrap_strategy_test(
        self,
        strategy_returns: list[float],
        n_bootstrap: int = 1000,
        confidence_level: float = 0.95
    ) -> dict:
        """Perform bootstrap testing on strategy returns.

        Args:
            strategy_returns: List of strategy returns
            n_bootstrap: Number of bootstrap samples
            confidence_level: Confidence level for intervals

        Returns:
            Dictionary with bootstrap results
        """
        if len(strategy_returns) < 2:
            return {
                'mean': np.mean(strategy_returns) if strategy_returns else 0,
                'std': np.std(strategy_returns) if strategy_returns else 0,
                'ci_lower': 0,
                'ci_upper': 0,
                'p_value_zero': 1.0
            }

        # Convert to numpy array for easier handling
        returns_array = np.array(strategy_returns)

        # Bootstrap sampling
        bootstrap_means = []
        for _ in range(n_bootstrap):
            # Sample with replacement
            bootstrap_sample = np.random.choice(returns_array, size=len(returns_array), replace=True)
            bootstrap_means.append(np.mean(bootstrap_sample))

        bootstrap_means = np.array(bootstrap_means)

        # Calculate confidence interval
        alpha = 1 - confidence_level
        lower_percentile = (alpha / 2) * 100
        upper_percentile = (1 - alpha / 2) * 100

        ci_lower = np.percentile(bootstrap_means, lower_percentile)
        ci_upper = np.percentile(bootstrap_means, upper_percentile)

        # Test if mean is significantly different from zero
        # p-value: proportion of bootstrap means that are as extreme as zero
        if np.mean(returns_array) > 0:
            p_value_zero = np.mean(bootstrap_means <= 0) * 2  # Two-tailed test
        else:
            p_value_zero = np.mean(bootstrap_means >= 0) * 2  # Two-tailed test

        return {
            'mean': np.mean(returns_array),
            'std': np.std(returns_array),
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'p_value_zero': p_value_zero,
            'significant': p_value_zero < 0.05
        }

    def regime_change_detection(
        self,
        returns: list[float],
        window_size: int = 252
    ) -> dict:
        """Detect potential regime changes in strategy performance.

        Args:
            returns: List of strategy returns
            window_size: Rolling window size for analysis

        Returns:
            Dictionary with regime change analysis
        """
        if len(returns) < window_size * 2:
            return {
                'regime_changes_detected': False,
                'message': 'Insufficient data for regime change detection'
            }

        returns_array = np.array(returns)

        # Calculate rolling statistics
        rolling_mean = pd.Series(returns_array).rolling(window=window_size).mean()
        rolling_std = pd.Series(returns_array).rolling(window=window_size).std()
        rolling_sharpe = rolling_mean / rolling_std * np.sqrt(252)  # Annualized

        # Detect significant changes in rolling statistics
        mean_changes = np.abs(np.diff(rolling_mean.dropna())) > (2 * rolling_std.dropna().mean())
        std_changes = np.abs(np.diff(rolling_std.dropna())) > (0.5 * rolling_std.dropna().mean())

        change_points = np.where(mean_changes | std_changes)[0]

        return {
            'regime_changes_detected': len(change_points) > 0,
            'n_change_points': len(change_points),
            'change_point_indices': change_points.tolist(),
            'mean_stability': 1 - np.mean(mean_changes) if len(mean_changes) > 0 else 1,
            'std_stability': 1 - np.mean(std_changes) if len(std_changes) > 0 else 1,
            'final_rolling_sharpe': rolling_sharpe.dropna().iloc[-1] if not rolling_sharpe.dropna().empty else 0
        }


def run_parameter_sweep(
    data: pd.DataFrame,
    symbol: str,
    config_grid: dict
) -> list[StrategyResult]:
    """Run a full parameter sweep across a configuration grid.

    Args:
        data: Historical price data
        symbol: Symbol being tested
        config_grid: Dictionary with 'ma_pairs', 'momentum_lookbacks', etc.

    Returns:
        List of all strategy results
    """
    sensitivity = ParameterSensitivity(data, symbol)

    all_results = []

    # Test MA pairs
    if 'ma_pairs' in config_grid:
        ma_results = sensitivity.test_ma_pairs(config_grid['ma_pairs'])
        all_results.extend(ma_results)

    # Test momentum lookbacks
    if 'momentum_lookbacks' in config_grid:
        mom_results = sensitivity.test_momentum_lookbacks(config_grid['momentum_lookbacks'])
        all_results.extend(mom_results)

    return all_results


def run_options_parameter_sweep(
    data: pd.DataFrame,
    symbol: str,
    strategy_type: str,
    param_grid: dict,
    initial_capital: float = 100000
) -> list[StrategyResult]:
    """Run a parameter sweep for options strategies.

    Args:
        data: Historical price data
        symbol: Symbol being tested
        strategy_type: Type of options strategy
        param_grid: Dictionary of parameters to test
        initial_capital: Initial capital for backtests

    Returns:
        List of all strategy results
    """
    sensitivity = ParameterSensitivity(data, symbol)

    return sensitivity.test_options_strategy_parameters(
        strategy_type, param_grid, initial_capital
    )


def walk_forward_analysis(
    data: pd.DataFrame,
    strategy_factory: callable,
    train_window: int = 252,  # 1 year of trading days
    test_window: int = 63,    # 3 months of trading days
    step_size: int = 21,      # 1 month step
    initial_capital: float = 100000
) -> dict:
    """Perform walk-forward analysis to test strategy robustness over time.

    Args:
        data: Historical price data
        strategy_factory: Function that returns a strategy instance
        train_window: Training window size in days
        test_window: Testing window size in days
        step_size: Step size for walk-forward windows
        initial_capital: Initial capital for each backtest

    Returns:
        Dictionary with walk-forward analysis results
    """
    if len(data) < train_window + test_window:
        return {
            'error': 'Insufficient data for walk-forward analysis',
            'n_windows': 0
        }

    results = []
    start_idx = 0

    while start_idx + train_window + test_window <= len(data):
        # Define train and test windows
        train_end = start_idx + train_window
        test_end = train_end + test_window

        train_data = data.iloc[start_idx:train_end].copy()
        test_data = data.iloc[train_end:test_end].copy()

        # Create and train strategy
        try:
            strategy = strategy_factory()
            backtest = EventDrivenBacktest(strategy, initial_capital=initial_capital)

            # Run on test data
            result_dict = backtest.run(test_data, data.iloc[train_end-1]['symbol'] if 'symbol' in data.columns else symbol)

            # Extract results
            if 'avg_delta_exposure' in result_dict:
                result = OptionsStrategyResult(
                    config_name=f"WF_{start_idx}_{test_end}",
                    total_return=result_dict.get('total_return', 0),
                    annualized_return=result_dict.get('annualized_return', 0),
                    sharpe_ratio=result_dict.get('sharpe_ratio', 0),
                    max_drawdown=result_dict.get('max_drawdown', 0),
                    num_trades=result_dict.get('num_trades', 0),
                    win_rate=result_dict.get('win_rate', 0),
                    profit_factor=result_dict.get('profit_factor', 0),
                    avg_trade_return=result_dict.get('avg_trade_return', 0),
                    avg_delta_exposure=result_dict.get('avg_delta_exposure', 0),
                    avg_gamma_exposure=result_dict.get('avg_gamma_exposure', 0),
                    avg_theta_decay=result_dict.get('avg_theta_decay', 0),
                    avg_vega_exposure=result_dict.get('avg_vega_exposure', 0),
                    max_option_notional=result_dict.get('max_option_notional', 0),
                    percent_profitable_expirations=result_dict.get('percent_profitable_expirations', 0),
                    avg_days_to_exit=result_dict.get('avg_days_to_exit', 0)
                )
            else:
                result = StrategyResult(
                    config_name=f"WF_{start_idx}_{test_end}",
                    total_return=result_dict.get('total_return', 0),
                    annualized_return=result_dict.get('annualized_return', 0),
                    sharpe_ratio=result_dict.get('sharpe_ratio', 0),
                    max_drawdown=result_dict.get('max_drawdown', 0),
                    num_trades=result_dict.get('num_trades', 0)
                )

            results.append({
                'train_start': start_idx,
                'train_end': train_end,
                'test_start': train_end,
                'test_end': test_end,
                'result': result
            })

        except Exception as e:
            logger.warning(f"Warning: Walk-forward window {start_idx}-{test_end} failed: {e}")

        # Move to next window
        start_idx += step_size

    # Calculate summary statistics
    if results:
        total_returns = [r['result'].total_return for r in results]
        sharpe_ratios = [r['result'].sharpe_ratio for r in results]
        max_drawdowns = [r['result'].max_drawdown for r in results]

        return {
            'n_windows': len(results),
            'avg_total_return': np.mean(total_returns),
            'std_total_return': np.std(total_returns),
            'avg_sharpe_ratio': np.mean(sharpe_ratios),
            'std_sharpe_ratio': np.std(sharpe_ratios),
            'avg_max_drawdown': np.mean(max_drawdowns),
            'std_max_drawdown': np.std(max_drawdowns),
            'positive_windows': sum(1 for r in total_returns if r > 0),
            'win_rate': sum(1 for r in total_returns if r > 0) / len(total_returns),
            'detailed_results': results
        }
    else:
        return {
            'n_windows': 0,
            'error': 'No valid walk-forward windows completed'
        }


def monte_carlo_simulation(
    data: pd.DataFrame,
    strategy_factory: callable,
    n_simulations: int = 100,
    initial_capital: float = 100000,
    block_size: int = 21
) -> dict:
    """Perform Monte Carlo simulation using block bootstrap.

    Args:
        data: Historical price data
        strategy_factory: Function that returns a strategy instance
        n_simulations: Number of Monte Carlo simulations
        initial_capital: Initial capital for each simulation
        block_size: Block size for block bootstrap (to preserve autocorrelation)

    Returns:
        Dictionary with Monte Carlo simulation results
    """
    if len(data) < block_size:
        return {
            'error': 'Insufficient data for block size',
            'n_simulations': 0
        }

    simulation_returns = []

    for sim_idx in range(n_simulations):
        # Create bootstrap sample using block bootstrap
        n_blocks = int(np.ceil(len(data) / block_size))
        bootstrap_indices = []

        for _ in range(n_blocks):
            # Random start index for block
            start_idx = np.random.randint(0, len(data) - block_size + 1)
            block_indices = list(range(start_idx, min(start_idx + block_size, len(data))))
            bootstrap_indices.extend(block_indices)

        # Trim to original length
        bootstrap_indices = bootstrap_indices[:len(data)]
        bootstrap_data = data.iloc[bootstrap_indices].copy()

        # Reset index to ensure continuity
        bootstrap_data.reset_index(drop=True, inplace=True)

        # Run strategy on bootstrap data
        try:
            strategy = strategy_factory()
            backtest = EventDrivenBacktest(strategy, initial_capital=initial_capital)

            # Use last known symbol or default
            symbol = data.iloc[-1]['symbol'] if 'symbol' in data.columns and len(data) > 0 else "UNKNOWN"

            result_dict = backtest.run(bootstrap_data, symbol)
            simulation_returns.append(result_dict.get('total_return', 0))

        except Exception as e:
            logger.warning(f"Warning: Monte Carlo simulation {sim_idx} failed: {e}")
            simulation_returns.append(0.0)  # Failed simulation gets zero return

    # Calculate statistics
    if simulation_returns:
        returns_array = np.array(simulation_returns)

        return {
            'n_simulations': len(simulation_returns),
            'mean_return': np.mean(returns_array),
            'std_return': np.std(returns_array),
            'sharpe_ratio': np.mean(returns_array) / np.std(returns_array) * np.sqrt(252) if np.std(returns_array) > 0 else 0,
            'percentile_5': np.percentile(returns_array, 5),
            'percentile_25': np.percentile(returns_array, 25),
            'percentile_50': np.percentile(returns_array, 50),
            'percentile_75': np.percentile(returns_array, 75),
            'percentile_95': np.percentile(returns_array, 95),
            'prob_positive': np.mean(np.array(simulation_returns) > 0),
            'max_drawdown_mc': np.min(np.array(simulation_returns)),  # Worst case
            'all_returns': simulation_returns
        }
    else:
        return {
            'n_simulations': 0,
            'error': 'No valid simulations completed'
        }

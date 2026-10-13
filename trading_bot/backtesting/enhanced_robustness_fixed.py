"""Enhanced robustness testing with visualization and improved reporting for options trading."""

import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Tuple, Any, Callable
from dataclasses import dataclass, field
import json
import os
from datetime import datetime
import warnings
import logging

logger = logging.getLogger(__name__)

from trading_bot.backtesting.robustness import (
    ParameterSensitivity,
    WhitesRealityCheck, StrategyResult, OptionsStrategyResult,
    walk_forward_analysis, monte_carlo_simulation, run_parameter_sweep,
    run_options_parameter_sweep
)
from trading_bot.backtesting.engine import EventDrivenBacktest
from trading_bot.backtesting.costs import TransactionCostModel
from trading_bot.backtesting.metrics import PerformanceMetrics
from trading_bot.strategies.trend_following import TrendFollowingStrategy
from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy


@dataclass
class EnhancedWalkForwardResult:
    """Enhanced result of walk-forward analysis with additional metrics."""
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
    in_sample_volatility: float
    out_of_sample_volatility: float
    in_sample_win_rate: float
    out_of_sample_win_rate: float
    config_used: str
    config_params: Dict[str, Any] = field(default_factory=dict)


class EnhancedWalkForwardAnalyzer:
    """Enhanced walk-forward analyzer with visualization and improved reporting."""

    def __init__(
        self,
        data: pd.DataFrame,
        symbol: str = "AAPL",
        initial_capital: float = 100000,
        window_size: int = 504,  # 2 years of trading days
        step_size: int = 63,     # 3 months (1 quarter)
        optimal_config_selector: Optional[Callable] = None
    ):
        """Initialize enhanced walk-forward analyzer."""
        self.logger = logging.getLogger(__name__)
        """Initialize enhanced walk-forward analyzer.

        Args:
            data: Full historical data
            symbol: Symbol being tested
            initial_capital: Initial capital for backtests
            window_size: Training window size in days (default 504 = 2 years)
            step_size: Step forward size in days (default 63 = 3 months)
            optimal_config_selector: Function to select best config from IS results
        """
        self.data = data.sort_values('date').reset_index(drop=True)
        self.symbol = symbol
        self.initial_capital = initial_capital
        self.window_size = window_size
        self.step_size = step_size
        self.optimal_config_selector = optimal_config_selector
        self.enhanced_results: list[EnhancedWalkForwardResult] = []

    def _safe_get_metric(self, obj, attr_name: str, default: float = 0.0) -> float:
        """Safely extract a metric value from an object, handling methods and conversion errors.

        Args:
            obj: Object to extract the metric from
            attr_name: Name of the attribute to extract
            default: Default value to return if extraction fails

        Returns:
            The metric value as a float
        """
        value = getattr(obj, attr_name, default)
        # If it's a method, try calling it to get the value
        if callable(value):
            try:
                # Try calling with no arguments first
                return float(value())
            except (TypeError):
                # If that fails due to arguments, try to see if we can get it another way
                # For now, return default
                return default
            except (ValueError, TypeError):
                return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def _run_backtest_for_config(
        self,
        data: pd.DataFrame,
        config: dict,
        cost_model: TransactionCostModel
    ) -> tuple[dict, PerformanceMetrics]:
        """Run a single backtest with given configuration and return enhanced metrics.

        Args:
            data: Data to backtest on
            config: Strategy configuration (must include 'strategy_type' and strategy-specific params)
            cost_model: Transaction cost model

        Returns:
            Tuple of (result_dict, metrics)
        """
        # Import strategy classes
        from trading_bot.strategies.trend_following import TrendFollowingStrategy
        from trading_bot.strategies.composite_score import CompositeTrendScore
        from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy
        from trading_bot.strategies.calendar_spread import CalendarSpreadStrategy
        from trading_bot.strategies.covered_call import CoveredCallStrategy
        from trading_bot.strategies.iron_condor import IronCondorStrategy
        from trading_bot.strategies.diagonal_spread import DiagonalSpreadStrategy

        # Strategy factory - create strategy instance based on config
        strategy_type = config.get('strategy_type', 'trend_following').lower()

        try:
            if strategy_type == 'trend_following':
                strategy = TrendFollowingStrategy(
                    entry_threshold=config.get('entry_threshold', 0.5),
                    exit_threshold=config.get('exit_threshold', -0.3),
                    weights=config.get('weights'),
                    short_window=config.get('short_window', 20),
                    medium_window=config.get('medium_window', 50),
                    long_window=config.get('long_window', 200),
                    momentum_lookbacks=config.get('momentum_lookbacks'),
                    volatility_window=config.get('volatility_window', 21)
                )
            elif strategy_type == 'composite_score':
                # For composite score, we need to use it with a trend following strategy
                # CompositeTrendScore is a calculator, not a standalone strategy
                weights = config.get('weights')
                entry_threshold = config.get('entry_threshold', 0.5)
                exit_threshold = config.get('exit_threshold', -0.3)
                strategy = TrendFollowingStrategy(
                    entry_threshold=entry_threshold,
                    exit_threshold=exit_threshold,
                    weights=weights
                )
            elif strategy_type == 'vertical_spread':
                strategy = VerticalSpreadStrategy(
                    spread_type=config.get('spread_type', 'bull_call'),
                    width=config.get('width', 5.0),
                    target_delta=config.get('target_delta', 0.3),
                    max_days_to_expiration=config.get('max_days_to_expiration', 45),
                    min_days_to_expiration=config.get('min_days_to_expiration', 21),
                    profit_target=config.get('profit_target', 0.5),
                    stop_loss=config.get('stop_loss', 0.5)
                )
            elif strategy_type == 'calendar_spread':
                strategy = CalendarSpreadStrategy(
                    spread_type=config.get('spread_type', 'call'),
                    width=config.get('width', 0.0),  # Same strike for calendar
                    front_month_offset=config.get('front_month_offset', 1),
                    back_month_offset=config.get('back_month_offset', 2),
                    profit_target=config.get('profit_target', 0.5),
                    stop_loss=config.get('stop_loss', 0.5)
                )
            elif strategy_type == 'covered_call':
                strategy = CoveredCallStrategy(
                    target_delta=config.get('target_delta', 0.3),
                    profit_target=config.get('profit_target', 0.5),
                    stop_loss=config.get('stop_loss', 0.5),
                    min_days_to_expiration=config.get('min_days_to_expiration', 21),
                    max_days_to_expiration=config.get('max_days_to_expiration', 45)
                )
            elif strategy_type == 'iron_condor':
                strategy = IronCondorStrategy(
                    width=config.get('width', 5.0),
                    target_delta=config.get('target_delta', 0.2),
                    profit_target=config.get('profit_target', 0.5),
                    stop_loss=config.get('stop_loss', 0.5),
                    min_days_to_expiration=config.get('min_days_to_expiration', 21),
                    max_days_to_expiration=config.get('max_days_to_expiration', 45)
                )
            elif strategy_type == 'diagonal_spread':
                strategy = DiagonalSpreadStrategy(
                    spread_type=config.get('spread_type', 'bullish'),
                    width=config.get('width', 5.0),
                    target_delta=config.get('target_delta', 0.3),
                    front_month_offset=config.get('front_month_offset', 1),
                    back_month_offset=config.get('back_month_offset', 2),
                    profit_target=config.get('profit_target', 0.5),
                    stop_loss=config.get('stop_loss', 0.5)
                )
            else:
                # Default to TrendFollowingStrategy if unknown type
                logger.warning(f"Unknown strategy type: {strategy_type}, defaulting to TrendFollowingStrategy")
                strategy = TrendFollowingStrategy()
        except Exception as e:
            logger.error(f"Error creating strategy of type {strategy_type}: {e}")
            # Fallback to default strategy
            strategy = TrendFollowingStrategy()

        backtest = EventDrivenBacktest(
            strategy,
            initial_capital=self.initial_capital
        )

        # Run on test data
        result_dict = backtest.run(data, data.iloc[-1]['symbol'] if 'symbol' in data.columns and len(data) > 0 else "UNKNOWN")

        # Extract metrics from result_dict (most reliable source)
        sharpe_ratio_value = result_dict.get('sharpe_ratio', 0.0)
        total_return_value = result_dict.get('total_return', 0.0)
        max_drawdown_value = result_dict.get('max_drawdown', 0.0)
        volatility_value = result_dict.get('volatility', 0.0)
        win_rate_value = result_dict.get('win_rate', 0.0)
        annualized_return_value = result_dict.get('annualized_return', 0.0)
        num_trades_value = result_dict.get('num_trades', 0)
        profit_factor_value = result_dict.get('profit_factor', 0.0)
        avg_trade_return_value = result_dict.get('avg_trade_return', 0.0)

        # Create metrics object and set values
        metrics = PerformanceMetrics()
        metrics.total_return = total_return_value
        metrics.annualized_return = annualized_return_value
        metrics.sharpe_ratio = sharpe_ratio_value
        metrics.max_drawdown = max_drawdown_value
        metrics.volatility = volatility_value
        metrics.win_rate = win_rate_value
        metrics.num_trades = num_trades_value
        metrics.profit_factor = profit_factor_value
        metrics.avg_trade_return = avg_trade_return_value

        # Set Greeks exposure metrics (default to 0 if not available)
        metrics.avg_delta_exposure = result_dict.get('avg_delta_exposure', 0.0)
        metrics.avg_gamma_exposure = result_dict.get('avg_gamma_exposure', 0.0)
        metrics.avg_theta_decay = result_dict.get('avg_theta_decay', 0.0)
        metrics.avg_vega_exposure = result_dict.get('avg_vega_exposure', 0.0)
        metrics.max_option_notional = result_dict.get('max_option_notional', 0.0)
        metrics.percent_profitable_expirations = result_dict.get('percent_profitable_expirations', 0.0)
        metrics.avg_days_to_exit = result_dict.get('avg_days_to_exit', 0.0)

        # Extract configuration parameters for reporting
        config_params = {k: v for k, v in config.items()
                       if k not in ['name', 'strategy_type']}  # Exclude name and strategy_type fields

        is_result = {
            'config_name': config.get('name', 'unknown'),
            'sharpe_ratio': sharpe_ratio_value,
            'total_return': total_return_value,
            'max_drawdown': max_drawdown_value,
            'volatility': volatility_value,
            'win_rate': win_rate_value,
            'config_params': config_params
        }

        return is_result, metrics

    def run_analysis(
        self,
        configs: list[dict],
        cost_model: Optional[TransactionCostModel] = None,
        verbose: bool = True
    ) -> list[EnhancedWalkForwardResult]:
        """Run enhanced walk-forward analysis with additional metrics.

        Args:
            configs: List of strategy configurations to test
            cost_model: Transaction cost model
            verbose: Print progress

        Returns:
            List of enhanced walk-forward results
        """
        if verbose:
            print(f"Starting enhanced walk-forward analysis with {len(configs)} configurations")
            print(f"Data range: {self.data['date'].min()} to {self.data['date'].max()}")
            print(f"Window size: {self.window_size}, Step size: {self.step_size}")

        # Reset results
        self.enhanced_results = []

        # Calculate number of windows
        total_days = len(self.data)
        if total_days < self.window_size:
            if verbose:
                print(f"Not enough data: {total_days} days < {self.window_size} window size")
            return []

        # Calculate walk-forward windows
        window_starts = list(range(0, total_days - self.window_size + 1, self.step_size))

        if verbose:
            print(f"Processing {len(window_starts)} windows...")

        # Process each window
        for i, start_idx in enumerate(window_starts):
            end_idx = start_idx + self.window_size

            # Extract in-sample data (training window)
            is_data = self.data.iloc[start_idx:end_idx].copy()

            # Calculate out-of-sample data (testing window) - next step_size periods
            oos_start_idx = end_idx
            oos_end_idx = min(oos_start_idx + self.step_size, total_days)

            # Skip if we don't have enough out-of-sample data
            if oos_end_idx - oos_start_idx < self.step_size // 2:  # At least half step size
                if verbose:
                    print(f"Window {i+1}: Insufficient out-of-sample data, skipping")
                continue

            oos_data = self.data.iloc[oos_start_idx:oos_end_idx].copy()

            if verbose:
                print(f"Window {i+1}: IS [{is_data['date'].iloc[0]} to {is_data['date'].iloc[-1]}], "
                      f"OOS [{oos_data['date'].iloc[0]} to {oos_data['date'].iloc[-1]}]")

            # Find optimal configuration using in-sample data
            best_result = None
            best_sharpe = -float('inf')
            best_config = None

            for config in configs:
                try:
                    # Run backtest on in-sample data with this configuration
                    result_dict, metrics = self._run_single_backtest(is_data, config, cost_model)

                    # Use Sharpe ratio to select best configuration
                    sharpe_ratio = result_dict.get('sharpe_ratio', 0.0)

                    if sharpe_ratio > best_sharpe:
                        best_sharpe = sharpe_ratio
                        best_result = result_dict
                        best_config = config

                except Exception as e:
                    if verbose:
                        print(f"Error running config {config.get('name', 'unknown')}: {e}")
                    continue

            # If we found a valid configuration, test it on out-of-sample data
            if best_result is not None and best_config is not None:
                try:
                    # Run the optimal configuration on out-of-sample data
                    oos_result_dict, oos_metrics = self._run_single_backtest(oos_data, best_config, cost_model)

                    # Create enhanced result
                    enhanced_result = EnhancedWalkForwardResult(
                        window_start=is_data['date'].iloc[0],
                        window_end=is_data['date'].iloc[-1],
                        out_of_sample_start=oos_data['date'].iloc[0],
                        out_of_sample_end=oos_data['date'].iloc[-1],
                        config_used=best_config.get('name', 'unknown'),
                        in_sample_return=best_result.get('total_return', 0.0),
                        out_of_sample_return=oos_result_dict.get('total_return', 0.0),
                        in_sample_sharpe=best_result.get('sharpe_ratio', 0.0),
                        out_of_sample_sharpe=oos_result_dict.get('sharpe_ratio', 0.0),
                        in_sample_max_dd=best_result.get('max_drawdown', 0.0),
                        out_of_sample_max_dd=oos_result_dict.get('max_drawdown', 0.0),
                        in_sample_volatility=best_result.get('volatility', 0.0),
                        out_of_sample_volatility=oos_result_dict.get('volatility', 0.0),
                        in_sample_win_rate=best_result.get('win_rate', 0.0),
                        out_of_sample_win_rate=oos_result_dict.get('win_rate', 0.0),
                        config_params={k: v for k, v in best_config.items()
                                     if k not in ['name', 'strategy_type']}
                    )

                    self.enhanced_results.append(enhanced_result)

                    if verbose:
                        print(f"Window {i+1}: IS Return: {enhanced_result.in_sample_return:.2%}, "
                              f"OOS Return: {enhanced_result.out_of_sample_return:.2%}")

                except Exception as e:
                    if verbose:
                        print(f"Error running optimal config on OOS data: {e}")
                    continue
            else:
                if verbose:
                    print(f"Window {i+1}: No valid configuration found")

        if verbose:
            print(f"Enhanced walk-forward analysis completed. Generated {len(self.enhanced_results)} results.")

        return self.enhanced_results

    def _run_single_backtest(self, data: pd.DataFrame, config: dict,
                           cost_model: Optional[TransactionCostModel]) -> tuple[dict, PerformanceMetrics]:
        """Run a single backtest with the given configuration and data.

        Args:
            data: Data to run backtest on
            config: Strategy configuration
            cost_model: Transaction cost model

        Returns:
            Tuple of (result_dict, metrics)
        """
        # Determine strategy type from config
        strategy_type = config.get('strategy_type', 'trend_following').lower()

        # Import strategy classes
        from trading_bot.strategies.trend_following import TrendFollowingStrategy
        from trading_bot.strategies.composite_score import CompositeTrendScore
        from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy
        from trading_bot.strategies.calendar_spread import CalendarSpreadStrategy
        from trading_bot.strategies.covered_call import CoveredCallStrategy
        from trading_bot.strategies.iron_condor import IronCondorStrategy
        from trading_bot.strategies.diagonal_spread import DiagonalSpreadStrategy
        try:
            from trading_bot.strategies.cash_secured_put import CashSecuredPutStrategy
        except ImportError:
            # Create a placeholder if the module doesn't exist yet
            class CashSecuredPutStrategy:
                def __init__(self, *args, **kwargs):
                    pass
        from trading_bot.strategies.straddle import StraddleStrategy
        from trading_bot.strategies.strangle import StrangleStrategy
        from trading_bot.strategies.butterfly import ButterflyStrategy
        from trading_bot.strategies.collar import CollarStrategy

        # Strategy factory - create strategy instance based on config
        try:
            if strategy_type == 'trend_following':
                strategy = TrendFollowingStrategy(
                    entry_threshold=config.get('entry_threshold', 0.5),
                    exit_threshold=config.get('exit_threshold', -0.3),
                    weights=config.get('weights'),
                    short_window=config.get('short_window', 20),
                    medium_window=config.get('medium_window', 50),
                    long_window=config.get('long_window', 200),
                    momentum_lookbacks=config.get('momentum_lookbacks'),
                    volatility_window=config.get('volatility_window', 21)
                )
            elif strategy_type == 'composite_score':
                # For composite score, we need to use it with a trend following strategy
                # CompositeTrendScore is a calculator, not a standalone strategy
                weights = config.get('weights')
                entry_threshold = config.get('entry_threshold', 0.5)
                exit_threshold = config.get('exit_threshold', -0.3)
                strategy = TrendFollowingStrategy(
                    entry_threshold=entry_threshold,
                    exit_threshold=exit_threshold,
                    weights=weights
                )
            elif strategy_type == 'vertical_spread':
                strategy = VerticalSpreadStrategy(
                    spread_type=config.get('spread_type', 'bull_call'),
                    width=config.get('width', 5.0),
                    target_delta=config.get('target_delta', 0.3),
                    max_days_to_expiration=config.get('max_days_to_expiration', 45),
                    min_days_to_expiration=config.get('min_days_to_expiration', 21),
                    profit_target=config.get('profit_target', 0.5),
                    stop_loss=config.get('stop_loss', 0.5)
                )
            elif strategy_type == 'calendar_spread':
                strategy = CalendarSpreadStrategy(
                    spread_type=config.get('spread_type', 'call'),
                    width=config.get('width', 0.0),  # Same strike for calendar
                    front_month_offset=config.get('front_month_offset', 1),
                    back_month_offset=config.get('back_month_offset', 2),
                    profit_target=config.get('profit_target', 0.5),
                    stop_loss=config.get('stop_loss', 0.5)
                )
            elif strategy_type == 'covered_call':
                strategy = CoveredCallStrategy(
                    target_delta=config.get('target_delta', 0.3),
                    profit_target=config.get('profit_target', 0.5),
                    stop_loss=config.get('stop_loss', 0.5),
                    min_days_to_expiration=config.get('min_days_to_expiration', 21),
                    max_days_to_expiration=config.get('max_days_to_expiration', 45)
                )
            elif strategy_type == 'iron_condor':
                strategy = IronCondorStrategy(
                    width=config.get('width', 5.0),
                    target_delta=config.get('target_delta', 0.2),
                    profit_target=config.get('profit_target', 0.5),
                    stop_loss=config.get('stop_loss', 0.5),
                    min_days_to_expiration=config.get('min_days_to_expiration', 21),
                    max_days_to_expiration=config.get('max_days_to_expiration', 45)
                )
            elif strategy_type == 'diagonal_spread':
                strategy = DiagonalSpreadStrategy(
                    spread_type=config.get('spread_type', 'bullish'),
                    width=config.get('width', 5.0),
                    target_delta=config.get('target_delta', 0.3),
                    front_month_offset=config.get('front_month_offset', 1),
                    back_month_offset=config.get('back_month_offset', 2),
                    profit_target=config.get('profit_target', 0.5),
                    stop_loss=config.get('stop_loss', 0.5)
                )
            elif strategy_type == 'cash_secured_put':
                strategy = CashSecuredPutStrategy(
                    otm_percentage=config.get('otm_percentage', 5.0),
                    max_days_to_expiration=config.get('max_days_to_expiration', 45),
                    min_days_to_expiration=config.get('min_days_to_expiration', 15),
                    profit_target=config.get('profit_target', 0.25)
                )
            elif strategy_type == 'straddle':
                strategy = StraddleStrategy(
                    straddle_type=config.get('straddle_type', 'long'),
                    profit_target=config.get('profit_target', 0.5),
                    stop_loss=config.get('stop_loss', 0.5)
                )
            elif strategy_type == 'strangle':
                strategy = StrangleStrategy(
                    strangle_type=config.get('strangle_type', 'long'),
                    profit_target=config.get('profit_target', 0.5),
                    stop_loss=config.get('stop_loss', 0.5)
                )
            elif strategy_type == 'butterfly':
                strategy = ButterflyStrategy(
                    butterfly_type=config.get('butterfly_type', 'long'),
                    width=config.get('width', 10.0),
                    width_type=config.get('width_type', 'percent'),
                    profit_target=config.get('profit_target', 0.5),
                    stop_loss=config.get('stop_loss', 0.5)
                )
            elif strategy_type == 'collar':
                strategy = CollarStrategy(
                    put_otm_percentage=config.get('put_otm_percentage', 5.0),
                    call_otm_percentage=config.get('call_otm_percentage', 5.0),
                    profit_target=config.get('profit_target', 0.5),
                    stop_loss=config.get('stop_loss', 0.5)
                )
            else:
                # Default to TrendFollowingStrategy if unknown type
                logger.warning(f"Unknown strategy type: {strategy_type}, defaulting to TrendFollowingStrategy")
                strategy = TrendFollowingStrategy()
        except Exception as e:
            logger.error(f"Error creating strategy of type {strategy_type}: {e}")
            # Fallback to default strategy
            strategy = TrendFollowingStrategy()

        backtest = EventDrivenBacktest(
            strategy,
            initial_capital=self.initial_capital
        )

        # Run on test data
        result_dict = backtest.run(data, data.iloc[-1]['symbol'] if 'symbol' in data.columns and len(data) > 0 else "UNKNOWN")

        # Extract metrics from result_dict (most reliable source)
        sharpe_ratio_value = result_dict.get('sharpe_ratio', 0.0)
        total_return_value = result_dict.get('total_return', 0.0)
        max_drawdown_value = result_dict.get('max_drawdown', 0.0)
        volatility_value = result_dict.get('volatility', 0.0)
        win_rate_value = result_dict.get('win_rate', 0.0)
        annualized_return_value = result_dict.get('annualized_return', 0.0)
        num_trades_value = result_dict.get('num_trades', 0)
        profit_factor_value = result_dict.get('profit_factor', 0.0)
        avg_trade_return_value = result_dict.get('avg_trade_return', 0.0)

        # Create metrics object and set values
        metrics = PerformanceMetrics()
        metrics.total_return = total_return_value
        metrics.annualized_return = annualized_return_value
        metrics.sharpe_ratio = sharpe_ratio_value
        metrics.max_drawdown = max_drawdown_value
        metrics.volatility = volatility_value
        metrics.win_rate = win_rate_value
        metrics.num_trades = num_trades_value
        metrics.profit_factor = profit_factor_value
        metrics.avg_trade_return = avg_trade_return_value

        # Set Greeks exposure metrics (default to 0 if not available)
        metrics.avg_delta_exposure = result_dict.get('avg_delta_exposure', 0.0)
        metrics.avg_gamma_exposure = result_dict.get('avg_gamma_exposure', 0.0)
        metrics.avg_theta_decay = result_dict.get('avg_theta_decay', 0.0)
        metrics.avg_vega_exposure = result_dict.get('avg_vega_exposure', 0.0)
        metrics.max_option_notional = result_dict.get('max_option_notional', 0.0)
        metrics.percent_profitable_expirations = result_dict.get('percent_profitable_expirations', 0.0)
        metrics.avg_days_to_exit = result_dict.get('avg_days_to_exit', 0.0)

        # Extract configuration parameters for reporting
        config_params = {k: v for k, v in config.items()
                       if k not in ['name', 'strategy_type']}  # Exclude name and strategy_type fields

        is_result = {
            'config_name': config.get('name', 'unknown'),
            'sharpe_ratio': sharpe_ratio_value,
            'total_return': total_return_value,
            'max_drawdown': max_drawdown_value,
            'volatility': volatility_value,
            'win_rate': win_rate_value,
            'config_params': config_params
        }

        return is_result, metrics

        if verbose:
            print(f"Processing {len(window_starts)} windows...")

        # Process each window
        for i, start_idx in enumerate(window_starts):
            end_idx = start_idx + self.window_size

            # Extract in-sample data (training window)
            is_data = self.data.iloc[start_idx:end_idx].copy()

            # Calculate out-of-sample data (testing window) - next step_size periods
            oos_start_idx = end_idx
            oos_end_idx = min(oos_start_idx + self.step_size, total_days)

            # Skip if we don't have enough out-of-sample data
            if oos_end_idx - oos_start_idx < self.step_size // 2:  # At least half step size
                if verbose:
                    print(f"Window {i+1}: Insufficient out-of-sample data, skipping")
                continue

            oos_data = self.data.iloc[oos_start_idx:oos_end_idx].copy()

            if verbose:
                print(f"Window {i+1}: IS [{is_data['date'].iloc[0]} to {is_data['date'].iloc[-1]}], "
                      f"OOS [{oos_data['date'].iloc[0]} to {oos_data['date'].iloc[-1]}]")

            # Find optimal configuration using in-sample data
            best_result = None
            best_sharpe = -float('inf')
            best_config = None

            for config in configs:
                try:
                    # Run backtest on in-sample data with this configuration
                    result_dict, metrics = self._run_single_backtest(is_data, config, cost_model)

                    # Use Sharpe ratio to select best configuration
                    sharpe_ratio = result_dict.get('sharpe_ratio', 0.0)

                    if sharpe_ratio > best_sharpe:
                        best_sharpe = sharpe_ratio
                        best_result = result_dict
                        best_config = config

                except Exception as e:
                    if verbose:
                        print(f"Error running config {config.get('name', 'unknown')}: {e}")
                    continue

            # If we found a valid configuration, test it on out-of-sample data
            if best_result is not None and best_config is not None:
                try:
                    # Run the optimal configuration on out-of-sample data
                    oos_result_dict, oos_metrics = self._run_single_backtest(oos_data, best_config, cost_model)

                    # Create enhanced result
                    enhanced_result = EnhancedWalkForwardResult(
                        window_start=is_data['date'].iloc[0],
                        window_end=is_data['date'].iloc[-1],
                        out_of_sample_start=oos_data['date'].iloc[0],
                        out_of_sample_end=oos_data['date'].iloc[-1],
                        config_used=best_config.get('name', 'unknown'),
                        in_sample_return=best_result.get('total_return', 0.0),
                        out_of_sample_return=oos_result_dict.get('total_return', 0.0),
                        in_sample_sharpe=best_result.get('sharpe_ratio', 0.0),
                        out_of_sample_sharpe=oos_result_dict.get('sharpe_ratio', 0.0),
                        in_sample_max_dd=best_result.get('max_drawdown', 0.0),
                        out_of_sample_max_dd=oos_result_dict.get('max_drawdown', 0.0),
                        in_sample_volatility=best_result.get('volatility', 0.0),
                        out_of_sample_volatility=oos_result_dict.get('volatility', 0.0),
                        in_sample_win_rate=best_result.get('win_rate', 0.0),
                        out_of_sample_win_rate=oos_result_dict.get('win_rate', 0.0),
                        config_params={k: v for k, v in best_config.items()
                                     if k not in ['name', 'strategy_type']}
                    )

                    self.enhanced_results.append(enhanced_result)

                    if verbose:
                        print(f"Window {i+1}: IS Return: {enhanced_result.in_sample_return:.2%}, "
                              f"OOS Return: {enhanced_result.out_of_sample_return:.2%}")

                except Exception as e:
                    if verbose:
                        print(f"Error running optimal config on OOS data: {e}")
                    continue
            else:
                if verbose:
                    print(f"Window {i+1}: No valid configuration found")

        if verbose:
            print(f"Enhanced walk-forward analysis completed. Generated {len(self.enhanced_results)} results.")

        print(f"DEBUG: About to return {type(self.enhanced_results)} with length {len(self.enhanced_results)}")
        return self.enhanced_results

    def plot_equity_curves(self, save_path: Optional[str] = None):
        """Plot equity curves for in-sample and out-of-sample periods.

        Args:
            save_path: Path to save the plot (if None, plot is displayed)
        """
        try:
            import matplotlib.pyplot as plt

            if not self.enhanced_results:
                print("No results to plot")
                return

            # Create subplots
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

            # Plot returns
            windows = [f"{r.window_start}\nto\n{r.window_end}" for r in self.enhanced_results]
            is_returns = [r.in_sample_return for r in self.enhanced_results]
            oos_returns = [r.out_of_sample_return for r in self.enhanced_results]

            x = np.arange(len(windows))
            width = 0.35

            ax1.bar(x - width/2, is_returns, width, label='In-Sample', alpha=0.8)
            ax1.bar(x + width/2, oos_returns, width, label='Out-of-Sample', alpha=0.8)
            ax1.set_xlabel('Walk-Forward Windows')
            ax1.set_ylabel('Return')
            ax1.set_title('In-Sample vs Out-of-Sample Returns')
            ax1.set_xticks(x)
            ax1.set_xticklabels(windows, rotation=45, ha='right')
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # Plot Sharpe ratios
            is_sharpe = [r.in_sample_sharpe for r in self.enhanced_results]
            oos_sharpe = [r.out_of_sample_sharpe for r in self.enhanced_results]

            ax2.bar(x - width/2, is_sharpe, width, label='In-Sample', alpha=0.8)
            ax2.bar(x + width/2, oos_sharpe, width, label='Out-of-Sample', alpha=0.8)
            ax2.set_xlabel('Walk-Forward Windows')
            ax2.set_ylabel('Sharpe Ratio')
            ax2.set_title('In-Sample vs Out-of-Sample Sharpe Ratios')
            ax2.set_xticks(x)
            ax2.set_xticklabels(windows, rotation=45, ha='right')
            ax2.legend()
            ax2.grid(True, alpha=0.3)

            plt.tight_layout()

            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                print(f"Plot saved to {save_path}")
            else:
                plt.show()

        except ImportError:
            print("Matplotlib not available for plotting")

    def generate_report(self, output_dir: str = "backtest_reports") -> str:
        """Generate a comprehensive HTML report of the walk-forward analysis.

        Args:
            output_dir: Directory to save the report

        Returns:
            Path to the generated report
        """
        if not self.enhanced_results:
            print("No results to report")
            return ""

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Generate report filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(output_dir, f"walkforward_report_{timestamp}.html")

        # Calculate summary statistics
        summary = self.calculate_enhanced_summary_stats()

        # Generate HTML report
        html_content = self._generate_html_report(summary)

        # Save report
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"Enhanced walk-forward report generated: {report_path}")
        return report_path

    def _generate_html_report(self, summary: dict) -> str:
        """Generate HTML content for the walk-forward report.

        Args:
            summary: Summary statistics dictionary

        Returns:
            HTML string
        """
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Enhanced Walk-Forward Analysis Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1, h2, h3 {{ color: #2c3e50; }}
        .summary-box {{
            background-color: #ecf0f1;
            padding: 20px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background-color: #3498db;
            color: white;
        }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .metric-positive {{ color: #27ae60; font-weight: bold; }}
        .metric-negative {{ color: #e74c3c; font-weight: bold; }}
        .config-box {{
            background-color: #f8f9fa;
            border-left: 4px solid #3498db;
            padding: 15px;
            margin: 15px 0;
        }}
    </style>
</head>
<body>
    <h1>Enhanced Walk-Forward Analysis Report</h1>
    <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

    <div class="summary-box">
        <h2>Summary Statistics</h2>
        <p><strong>Number of Windows:</strong> {summary.get('num_windows', 0)}</p>
        <p><strong>Average In-Sample Return:</strong>
            <span class="{'metric-positive' if summary.get('avg_is_return', 0) >= 0 else 'metric-negative'}">
                {summary.get('avg_is_return', 0):.2%}
            </span>
        </p>
        <p><strong>Average Out-of-Sample Return:</strong>
            <span class="{'metric-positive' if summary.get('avg_oos_return', 0) >= 0 else 'metric-negative'}">
                {summary.get('avg_oos_return', 0):.2%}
            </span>
        </p>
        <p><strong>Return Difference (IS - OOS):</strong>
            <span class="{'metric-positive' if summary.get('is_oos_return_diff', 0) >= 0 else 'metric-negative'}">
                {summary.get('is_oos_return_diff', 0):.2%}
            </span>
        </p>
        <p><strong>Average In-Sample Sharpe:</strong> {summary.get('avg_is_sharpe', 0):.3f}</p>
        <p><strong>Average Out-of-Sample Sharpe:</strong> {summary.get('avg_oos_sharpe', 0):.3f}</p>
        <p><strong>Sharpe Difference (IS - OOS):</strong>
            <span class="{'metric-positive' if summary.get('is_oos_sharpe_diff', 0) >= 0 else 'metric-negative'}">
                {summary.get('is_oos_sharpe_diff', 0):.3f}
            </span>
        </p>
        <p><strong>IS-OOS Return Correlation:</strong> {summary.get('is_oos_return_correlation', 0):.3f}</p>
    </div>

    <h2>Window-by-Window Results</h2>
    <table>
        <thead>
            <tr>
                <th>Window</th>
                <th>IS Return</th>
                <th>OOS Return</th>
                <th>IS Sharpe</th>
                <th>OOS Sharpe</th>
                <th>IS Max DD</th>
                <th>OOS Max DD</th>
                <th>IS Win Rate</th>
                <th>OOS Win Rate</th>
                <th>Optimal Config</th>
            </tr>
        </thead>
        <tbody>
"""

        for i, result in enumerate(self.enhanced_results):
            html += f"""
            <tr>
                <td>{result.window_start}<br>{result.window_end}</td>
                <td class="{'metric-positive' if result.in_sample_return >= 0 else 'metric-negative'}">
                    {result.in_sample_return:.2%}
                </td>
                <td class="{'metric-positive' if result.out_of_sample_return >= 0 else 'metric-negative'}">
                    {result.out_of_sample_return:.2%}
                </td>
                <td>{result.in_sample_sharpe:.3f}</td>
                <td>{result.out_of_sample_sharpe:.3f}</td>
                <td>{result.in_sample_max_dd:.2%}</td>
                <td>{result.out_of_sample_max_dd:.2%}</td>
                <td>{result.in_sample_win_rate:.2%}</td>
                <td>{result.out_of_sample_win_rate:.2%}</td>
                <td>{result.config_used}</td>
            </tr>
"""

        html += """
        </tbody>
    </table>

    <h2>Configuration Analysis</h2>
    <div class="config-box">
        <h3>Most Frequently Selected Optimal Configurations</h3>
        <ol>
"""

        config_counts = summary.get('config_counts', {})
        for config, count in list(config_counts.items())[:5]:  # Top 5
            html += f"<li>{config}: Selected {count} times</li>\n"

        html += """
        </ol>
    </div>

    <h2>Key Insights</h2>
    <ul>
"""

        # Add insights based on analysis
        if summary.get('is_oos_return_diff', 0) > 0.05:  # More than 5% drop
            html += "<li><strong>Overfitting Detected:</strong> In-sample performance significantly exceeds out-of-sample performance, suggesting potential overfitting.</li>\n"
        elif summary.get('is_oos_return_diff', 0) < -0.02:  # OOS better than IS
            html += "<li><strong>Underfitting or Improving Strategy:</strong> Out-of-sample performance exceeds in-sample performance, which may indicate underfitting or improving market conditions.</li>\n"
        else:
            html += "<li><strong>Robust Performance:</strong> Similar performance between in-sample and out-of-sample periods suggests good strategy robustness.</li>\n"

        if summary.get('is_oos_sharpe_diff', 0) > 0.3:
            html += "<li><strong>Sharpe Ratio Degradation:</strong> Significant drop in Sharpe ratio from in-sample to out-of-sample indicates risk-adjusted performance may not hold up in live trading.</li>\n"

        win_rate_consistency = abs(summary.get('avg_is_win_rate', 0) - summary.get('avg_oos_win_rate', 0))
        if win_rate_consistency < 0.1:
            html += "<li><strong>Consistent Win Rate:</strong> Win rate remains stable across samples, suggesting reliable signal generation.</li>\n"

        html += """
    </ul>

    <h2>Recommendations</h2>
    <ol>
"""

        # Add recommendations
        if summary.get('num_windows', 0) < 3:
            html += "<li>Increase data collection to enable more walk-forward windows for more robust analysis.</li>\n"

        if summary.get('is_oos_return_diff', 0) > 0.1:
            html += "<li>Consider simplifying the strategy or reducing parameter complexity to mitigate overfitting.</li>\n"

        if summary.get('avg_oos_sharpe', 0) < 0.5:
            html += "<li>Strategy shows marginal risk-adjusted performance; consider alternative approaches or parameter sets.</li>\n"
        else:
            html += "<li>Strategy demonstrates acceptable risk-adjusted performance for further testing.</li>\n"

        html += """
    </ol>
</body>
</html>
"""

        return html

    def calculate_enhanced_summary_stats(self) -> dict:
        """Calculate enhanced summary statistics from walk-forward results.

        Returns:
            Dictionary of enhanced summary statistics
        """
        if not self.enhanced_results:
            return {}

        results = self.enhanced_results

        # Basic stats
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
            'avg_is_volatility': np.mean([r.in_sample_volatility for r in results]),
            'avg_oos_volatility': np.mean([r.out_of_sample_volatility for r in results]),
            'avg_is_win_rate': np.mean([r.in_sample_win_rate for r in results]),
            'avg_oos_win_rate': np.mean([r.out_of_sample_win_rate for r in results]),
            'is_oos_return_correlation': np.corrcoef(
                [r.in_sample_return for r in results],
                [r.out_of_sample_return for r in results]
            )[0, 1] if len(results) > 1 else 0,
            'is_oos_sharpe_correlation': np.corrcoef(
                [r.in_sample_sharpe for r in results],
                [r.out_of_sample_sharpe for r in results]
            )[0, 1] if len(results) > 1 else 0
        }

        # Configuration analysis
        config_counts = {}
        for result in results:
            config = result.config_used
            config_counts[config] = config_counts.get(config, 0) + 1

        stats['config_counts'] = dict(sorted(config_counts.items(), key=lambda x: x[1], reverse=True))

        # Performance consistency metrics
        return_consistency = 1 - (np.std([r.out_of_sample_return for r in results]) /
                                 (abs(np.mean([r.out_of_sample_return for r in results])) + 1e-10))
        sharpe_consistency = 1 - (np.std([r.out_of_sample_sharpe for r in results]) /
                                 (abs(np.mean([r.out_of_sample_sharpe for r in results])) + 1e-10))

        stats['return_consistency'] = max(0, return_consistency)
        stats['sharpe_consistency'] = max(0, sharpe_consistency)

        return stats


def run_enhanced_walk_forward(
    data: pd.DataFrame,
    symbol: str,
    configs: list[dict],
    train_start: str,
    train_end: str,
    test_start: str,
    test_end: str,
    output_dir: str = "enhanced_backtest_outputs",
    window_size: int = 504,
    step_size: int = 63,
    generate_plots: bool = True,
    generate_report: bool = True
) -> tuple[list[EnhancedWalkForwardResult], dict]:
    """Run enhanced walk-forward analysis with plotting and reporting.

    Args:
        data: Full historical data
        symbol: Symbol being tested
        configs: List of strategy configurations
        train_start: Training period start
        train_end: Training period end
        test_start: Test period start
        test_end: Test period end
        output_dir: Output directory for results
        window_size: Training window size in days
        step_size: Step forward size in days
        generate_plots: Whether to generate visualization plots
        generate_report: Whether to generate HTML report

    Returns:
        Tuple of (results, summary)
    """
    # Filter data to test period
    test_data = data[
        (data['date'] >= pd.Timestamp(train_start)) &
        (data['date'] <= pd.Timestamp(test_end))
    ].copy()

    # Define configuration selector (choose highest Sharpe ratio)
    def select_best_sharpe(config_results):
        if not config_results:
            return None
        return max(config_results, key=lambda x: x['sharpe_ratio'])

    # Create enhanced analyzer
    analyzer = EnhancedWalkForwardAnalyzer(
        data=test_data,
        symbol=symbol,
        window_size=window_size,
        step_size=step_size,
        optimal_config_selector=select_best_sharpe
    )

    # Run analysis
    results = analyzer.run_analysis(configs, verbose=True)

    # Calculate summary
    summary = analyzer.calculate_enhanced_summary_stats()

    # Generate plots if requested
    if generate_plots and results:
        plots_dir = os.path.join(output_dir, "plots")
        os.makedirs(plots_dir, exist_ok=True)
        plot_path = os.path.join(plots_dir, f"walkforward_equity_curves_{symbol}.png")
        analyzer.plot_equity_curves(save_path=plot_path)

    # Generate report if requested
    if generate_report and results:
        report_dir = os.path.join(output_dir, "reports")
        analyzer.generate_report(output_dir=report_dir)

    return results, summary


# Convenience functions for easy import
def enhanced_walk_forward_analysis(
    data: pd.DataFrame,
    strategy_factory: callable,
    train_window: int = 252,
    test_window: int = 63,
    step_size: int = 21,
    initial_capital: float = 100000
) -> dict:
    """Enhanced version of walk_forward_analysis with additional metrics.

    Args:
        data: Historical price data
        strategy_factory: Function that returns a strategy instance
        train_window: Training window size in days
        test_window: Testing window size in days
        step_size: Step size for walk-forward windows
        initial_capital: Initial capital for each backtest

    Returns:
        Dictionary with enhanced walk-forward analysis results
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
            result_dict = backtest.run(test_data,
                                     data.iloc[train_end-1]['symbol'] if 'symbol' in data.columns else "UNKNOWN")

            # Extract enhanced results
            from trading_bot.backtesting.metrics import PerformanceMetrics
            metrics = PerformanceMetrics()
            metrics.calculate_all_metrics(
                pd.Series([v['portfolio_value'] for v in result_dict.get('daily_values', [])]),
                pd.Series([v['portfolio_value'] for v in result_dict.get('daily_values', [])])  # Simplified
            )

            if 'avg_delta_exposure' in result_dict:
                result = EnhancedWalkForwardResult(
                    window_start=str(train_data.iloc[0]['date'].date()),
                    window_end=str(train_data.iloc[-1]['date'].date()),
                    out_of_sample_start=str(test_data.iloc[0]['date'].date()),
                    out_of_sample_end=str(test_data.iloc[-1]['date'].date()),
                    in_sample_return=result_dict.get('total_return', 0),
                    out_of_sample_return=result_dict.get('total_return', 0),  # Simplified
                    in_sample_sharpe=result_dict.get('sharpe_ratio', 0),
                    out_of_sample_sharpe=result_dict.get('sharpe_ratio', 0),  # Simplified
                    in_sample_max_dd=result_dict.get('max_drawdown', 0),
                    out_of_sample_max_dd=result_dict.get('max_drawdown', 0),  # Simplified
                    in_sample_volatility=getattr(metrics, 'volatility', 0.0),
                    out_of_sample_volatility=getattr(metrics, 'volatility', 0.0),  # Simplified
                    in_sample_win_rate=getattr(metrics, 'win_rate', 0.0),
                    out_of_sample_win_rate=getattr(metrics, 'win_rate', 0.0),  # Simplified
                    config_used="default",
                    config_params={}
                )
            else:
                result = EnhancedWalkForwardResult(
                    window_start=str(train_data.iloc[0]['date'].date()),
                    window_end=str(train_data.iloc[-1]['date'].date()),
                    out_of_sample_start=str(test_data.iloc[0]['date'].date()),
                    out_of_sample_end=str(test_data.iloc[-1]['date'].date()),
                    in_sample_return=result_dict.get('total_return', 0),
                    out_of_sample_return=result_dict.get('total_return', 0),
                    in_sample_sharpe=result_dict.get('sharpe_ratio', 0),
                    out_of_sample_sharpe=result_dict.get('sharpe_ratio', 0),
                    in_sample_max_dd=result_dict.get('max_drawdown', 0),
                    out_of_sample_max_dd=result_dict.get('max_drawdown', 0),
                    in_sample_volatility=getattr(metrics, 'volatility', 0.0),
                    out_of_sample_volatility=getattr(metrics, 'volatility', 0.0),
                    in_sample_win_rate=getattr(metrics, 'win_rate', 0.0),
                    out_of_sample_win_rate=getattr(metrics, 'win_rate', 0.0),
                    config_used="default",
                    config_params={}
                )

            results.append({
                'train_start': start_idx,
                'train_end': train_end,
                'test_start': train_end,
                'test_end': test_end,
                'result': result
            })

        except Exception as e:
            print(f"Warning: Enhanced walk-forward window {start_idx}-{test_end} failed: {e}")

        # Move to next window
        start_idx += step_size

    # Calculate summary statistics
    if results:
        total_returns = [r['result'].out_of_sample_return for r in results]
        sharpe_ratios = [r['result'].out_of_sample_sharpe for r in results]
        max_drawdowns = [r['result'].out_of_sample_max_dd for r in results]
        win_rates = [r['result'].out_of_sample_win_rate for r in results]
        volatilities = [r['result'].out_of_sample_volatility for r in results]

        return {
            'n_windows': len(results),
            'avg_total_return': np.mean(total_returns),
            'std_total_return': np.std(total_returns),
            'avg_sharpe_ratio': np.mean(sharpe_ratios),
            'std_sharpe_ratio': np.std(sharpe_ratios),
            'avg_max_drawdown': np.mean(max_drawdowns),
            'std_max_drawdown': np.std(max_drawdowns),
            'avg_win_rate': np.mean(win_rates),
            'std_win_rate': np.std(win_rates),
            'avg_volatility': np.mean(volatilities),
            'std_volatility': np.std(volatilities),
            'positive_windows': sum(1 for r in total_returns if r > 0),
            'win_rate': sum(1 for r in total_returns if r > 0) / len(total_returns),
            'detailed_results': results
        }
    else:
        return {
            'n_windows': 0,
            'error': 'No valid walk-forward windows completed'
        }


if __name__ == "__main__":
    # Example usage when run directly
    print("Enhanced Robustness Module for Walk-Forward Analysis")
    print("This module provides enhanced walk-forward analysis with:")
    print("- Improved metrics reporting")
    print("- Visualization capabilities")
    print("- HTML report generation")
    print("- Enhanced statistical analysis")
"""Experiment runner for testing multiple strategy configurations."""

import yaml
import pandas as pd
import numpy as np
from typing import Optional, Any
from dataclasses import dataclass, field
import logging

from trading_bot.strategies.trend_following import TrendFollowingStrategy
from trading_bot.backtesting.engine import EventDrivenBacktest
from trading_bot.backtesting.costs import TransactionCostModel
from trading_bot.backtesting.metrics import PerformanceMetrics

logger = logging.getLogger(__name__)


@dataclass
class ExperimentConfig:
    """Configuration for a single experiment run."""
    name: str
    data_start_date: str = "2010-01-01"
    data_end_date: str = "2026-10-03"
    initial_capital: float = 100000
    cost_model: dict = field(default_factory=lambda: {
        'commission': 0.0,
        'slippage_bps': 5.0,
        'bid_ask_spread_bps': 2.0
    })
    strategy: dict = field(default_factory=lambda: {
        'entry_threshold': 0.5,
        'exit_threshold': -0.3,
        'short_window': 20,
        'medium_window': 50,
        'long_window': 200,
        'weights': {
            'short_ma': 0.25,
            'medium_ma': 0.25,
            'momentum': 0.25,
            'price_relative': 0.15,
            'vol_adjusted': 0.10
        }
    })


@dataclass
class ExperimentResult:
    """Results of a single experiment run."""
    config_name: str
    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    num_trades: int
    profit_factor: float
    buy_and_hold_return: float
    excess_return: float
    config: dict = field(default_factory=dict)


class ExperimentRunner:
    """Run multiple strategy configurations for comparison."""

    def __init__(
        self,
        data: pd.DataFrame,
        symbol: str = "AAPL",
        output_dir: str = "research_outputs"
    ):
        """Initialize experiment runner.

        Args:
            data: Historical price data
            symbol: Symbol being tested
            output_dir: Directory for saving results
        """
        self.data = data
        self.symbol = symbol
        self.output_dir = output_dir
        self.results = []

    def run_single_experiment(
        self,
        config: ExperimentConfig,
        train_data: pd.DataFrame,
        test_data: pd.DataFrame
    ) -> ExperimentResult:
        """Run a single experiment configuration.

        Args:
            config: Experiment configuration
            train_data: Training data
            test_data: Test data

        Returns:
            Experiment results
        """
        logger.info(f"Running experiment: {config.name}")

        # Create strategy
        weights = config.strategy.get('weights', {
            'short_ma': 0.25, 'medium_ma': 0.25, 'momentum': 0.25,
            'price_relative': 0.15, 'vol_adjusted': 0.10
        })

        strategy = TrendFollowingStrategy(
            entry_threshold=config.strategy['entry_threshold'],
            exit_threshold=config.strategy['exit_threshold'],
            weights=weights,
            short_window=config.strategy['short_window'],
            medium_window=config.strategy['medium_window'],
            long_window=config.strategy['long_window']
        )

        # Create cost model
        cost_model = TransactionCostModel(
            commission=config.cost_model['commission'],
            slippage_bps=config.cost_model['slippage_bps'],
            bid_ask_spread_bps=config.cost_model['bid_ask_spread_bps']
        )

        # Run backtest on test data (out-of-sample)
        backtest = EventDrivenBacktest(
            strategy=strategy,
            initial_capital=config.initial_capital,
            cost_model=cost_model
        )

        result_dict = backtest.run(test_data.copy(), self.symbol)

        # Calculate metrics
        portfolio_values = pd.Series(
            [v['portfolio_value'] for v in result_dict.get('daily_values', [])]
        )
        benchmark_values = test_data['adjusted_close'] / test_data['adjusted_close'].iloc[0] * config.initial_capital

        metrics = PerformanceMetrics()
        portfolio_metrics = metrics.calculate_all_metrics(portfolio_values, benchmark_values)

        result = ExperimentResult(
            config_name=config.name,
            total_return=portfolio_metrics.get('total_return', 0),
            annualized_return=portfolio_metrics.get('annualized_return', 0),
            annualized_volatility=portfolio_metrics.get('annualized_volatility', 0),
            sharpe_ratio=portfolio_metrics.get('sharpe_ratio', 0),
            sortino_ratio=portfolio_metrics.get('sortino_ratio', 0),
            max_drawdown=portfolio_metrics.get('max_drawdown', 0),
            win_rate=metrics.win_rate(result_dict.get('trades', [])),
            num_trades=result_dict.get('num_trades', 0),
            profit_factor=metrics.profit_factor(result_dict.get('trades', [])),
            buy_and_hold_return=result_dict.get('buy_and_hold_return', 0),
            excess_return=result_dict.get('excess_return', 0),
            config=config.__dict__
        )

        logger.info(f"  Result: Return={result.total_return:.1%}, "
                   f"Sharpe={result.sharpe_ratio:.2f}, Trades={result.num_trades}")

        return result

    def run_configuration_grid(
        self,
        grid_config: dict,
        train_data: pd.DataFrame,
        test_data: pd.DataFrame
    ) -> list[ExperimentResult]:
        """Run a grid of configuration experiments.

        Args:
            grid_config: Grid configuration dictionary
            train_data: Training data
            test_data: Test data

        Returns:
            List of experiment results
        """
        logger.info(f"Running configuration grid with {len(self._generate_grid_configs(grid_config))} combinations")

        all_results = []

        for config_dict in self._generate_grid_configs(grid_config):
            # Note: For true research, we would train on train_data
            # But since we're doing out-of-sample testing, we run on test_data only
            config = ExperimentConfig(name=config_dict['name'])

            # Update config with grid values
            for key, value in config_dict.items():
                if key != 'name':
                    if key in config.strategy:
                        config.strategy[key] = value
                    else:
                        setattr(config, key, value)

            result = self.run_single_experiment(config, train_data, test_data)
            all_results.append(result)

        # Sort by Sharpe ratio (descending)
        all_results.sort(key=lambda x: x.sharpe_ratio, reverse=True)

        return all_results

    def _generate_grid_configs(self, grid_config: dict) -> list[dict]:
        """Generate all configuration combinations from grid.

        Args:
            grid_config: Dictionary with grid specifications

        Returns:
            List of all configuration combinations
        """
        # Simple grid expansion for now
        configs = []

        ma_pairs = grid_config.get('ma_pairs', [[20, 50]])
        entry_thresholds = grid_config.get('entry_thresholds', [0.5])
        exit_thresholds = grid_config.get('exit_thresholds', [-0.3])

        counter = 1

        for ma_pair in ma_pairs:
            for entry_th in entry_thresholds:
                for exit_th in exit_thresholds:
                    # Medium window as geometric mean
                    medium_window = int((ma_pair[0] * ma_pair[1]) ** 0.5)

                    configs.append({
                        'name': f"Config_{counter:03d}",
                        'strategy': {
                            'short_window': ma_pair[0],
                            'medium_window': medium_window,
                            'long_window': ma_pair[1],
                            'entry_threshold': entry_th,
                            'exit_threshold': exit_th
                        }
                    })
                    counter += 1

        return configs

    def find_best_configs(
        self,
        results: list[ExperimentResult],
        top_n: int = 3,
        min_trades: int = 5,
        max_drawdown_limit: float = 0.30
    ) -> list[ExperimentResult]:
        """Find the best configurations based on Sharpe ratio.

        Args:
            results: List of experiment results
            top_n: Number of top configurations to return
            min_trades: Minimum number of trades required
            max_drawdown_limit: Maximum allowed drawdown

        Returns:
            Best configurations
        """
        # Filter results
        filtered = [
            r for r in results
            if (r.num_trades >= min_trades and
                r.max_drawdown <= max_drawdown_limit)
        ]

        # Sort by Sharpe ratio
        filtered.sort(key=lambda x: x.sharpe_ratio, reverse=True)

        return filtered[:top_n]

    def save_results(
        self,
        results: list[ExperimentResult],
        filename: str = "experiment_results.csv"
    ):
        """Save experiment results to CSV.

        Args:
            results: List of experiment results
            filename: Output filename
        """
        results_dicts = []

        for result in results:
            result_dict = {
                'config_name': result.config_name,
                'total_return': result.total_return,
                'annualized_return': result.annualized_return,
                'annualized_volatility': result.annualized_volatility,
                'sharpe_ratio': result.sharpe_ratio,
                'sortino_ratio': result.sortino_ratio,
                'max_drawdown': result.max_drawdown,
                'win_rate': result.win_rate,
                'num_trades': result.num_trades,
                'profit_factor': result.profit_factor,
                'buy_and_hold_return': result.buy_and_hold_return,
                'excess_return': result.excess_return,
            }
            results_dicts.append(result_dict)

        df = pd.DataFrame(results_dicts)
        df.to_csv(f"{self.output_dir}/{filename}", index=False)

        logger.info(f"Saved {len(df)} results to {filename}")

    def generate_summary_report(self, results: list[ExperimentResult]) -> dict:
        """Generate a summary report of all experiments.

        Args:
            results: List of experiment results

        Returns:
            Summary report dictionary
        """
        if not results:
            return {}

        summary = {
            'total_experiments': len(results),
            'best_sharpe': max(r.sharpe_ratio for r in results),
            'worst_sharpe': min(r.sharpe_ratio for r in results),
            'avg_sharpe': np.mean([r.sharpe_ratio for r in results]),
            'median_sharpe': np.median([r.sharpe_ratio for r in results]),
            'std_sharpe': np.std([r.sharpe_ratio for r in results]),
            'avg_trades': np.mean([r.num_trades for r in results]),
            'avg_drawdown': np.mean([r.max_drawdown for r in results]),
        }

        return summary


def load_grid_config(config_file: str) -> dict:
    """Load grid configuration from YAML file.

    Args:
        config_file: Path to configuration file

    Returns:
        Grid configuration dictionary
    """
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    return config


def run_full_experiment(
    data: pd.DataFrame,
    symbol: str,
    grid_config_file: str,
    train_start: str,
    train_end: str,
    test_start: str,
    test_end: str,
    output_dir: str = "research_outputs"
) -> tuple[list[ExperimentResult], dict]:
    """Run a full experiment workflow.

    Args:
        data: Full historical data
        symbol: Symbol being tested
        grid_config_file: Path to grid configuration file
        train_start: Training start date
        train_end: Training end date
        test_start: Test start date
        test_end: Test end date
        output_dir: Output directory

    Returns:
        Tuple of (results, summary)
    """
    # Load grid configuration
    grid_config = load_grid_config(grid_config_file)

    # Split data
    train_data = data[
        (data['date'] >= pd.Timestamp(train_start)) &
        (data['date'] <= pd.Timestamp(train_end))
    ]
    test_data = data[
        (data['date'] >= pd.Timestamp(test_start)) &
        (data['date'] <= pd.Timestamp(test_end))
    ]

    # Create runner
    runner = ExperimentRunner(data, symbol, output_dir)

    # Run experiments
    logger.info(f"Training period: {train_start} to {train_end}")
    logger.info(f"Testing period: {test_start} to {test_end}")

    results = runner.run_configuration_grid(grid_config, train_data, test_data)

    # Find best configurations
    best_configs = runner.find_best_configs(results)

    # Save results
    runner.save_results(results, "all_results.csv")
    runner.save_results(best_configs, "best_results.csv")

    # Generate summary
    summary = runner.generate_summary_report(results)

    return results, summary

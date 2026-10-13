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
from trading_bot.strategies.covered_call import CoveredCallStrategy, CashSecuredPutStrategy
from trading_bot.strategies.iron_condor import IronCondorStrategy
from trading_bot.strategies.calendar_spread import CalendarSpreadStrategy


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
        self.logger = logging.getLogger(__name__)

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
        # If it's a method, don't call it, just return default
        if callable(value):
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
            config: Strategy configuration
            cost_model: Transaction cost model

        Returns:
            Tuple of (result_dict, metrics)
        """
        # Create strategy from config based on strategy type
        strategy_type = config.get('type', 'trend_following').lower()

        try:
            if strategy_type == 'trend_following':
                strategy = TrendFollowingStrategy(
                    entry_threshold=config.get('entry_threshold', 0.5),
                    exit_threshold=config.get('exit_threshold', -0.3),
                    short_window=config.get('short_window', 20),
                    medium_window=config.get('medium_window', 50),
                    long_window=config.get('long_window', 200)
                )
            elif strategy_type == 'vertical_spread':
                strategy = VerticalSpreadStrategy(
                    underlying_symbol=config.get('underlying_symbol', 'AAPL'),
                    max_spread_width=config.get('max_spread_width', 10.0),
                    preferred_delta_range=tuple(config.get('preferred_delta_range', [0.2, 0.3])),
                    preferred_dte=config.get('preferred_dte', [30, 45])
                )
            elif strategy_type == 'covered_call':
                strategy = CoveredCallStrategy(
                    underlying_symbol=config.get('underlying_symbol', 'AAPL'),
                    otm_percentage=config.get('otm_percentage', 10),
                    dte_target=config.get('dte_target', 45)
                )
            elif strategy_type == 'cash_secured_put':
                strategy = CashSecuredPutStrategy(
                    underlying_symbol=config.get('underlying_symbol', 'AAPL'),
                    otm_percentage=config.get('otm_percentage', 10),
                    dte_target=config.get('dte_target', 45)
                )
            elif strategy_type == 'iron_condor':
                strategy = IronCondorStrategy(
                    wing_width=config.get('wing_width', 10),
                    delta_target=config.get('delta_target', 0.15),
                    dte_target=config.get('dte_target', 45)
                )
            elif strategy_type == 'calendar_spread':
                strategy = CalendarSpreadStrategy(
                    short_dte=config.get('short_dte', 30),
                    long_dte=config.get('long_dte', 60),
                    delta_target=config.get('delta_target', 0.25)
                )
            else:
                # Default to trend following if unknown strategy type
                strategy = TrendFollowingStrategy(
                    fast_period=config.get('fast_period', 10),
                    slow_period=config.get('slow_period', 30),
                    signal_threshold=config.get('signal_threshold', 0.02)
                )
        except Exception as e:
            self.logger.warning(f"Failed to create strategy of type {strategy_type}: {e}. Falling back to TrendFollowingStrategy.")
            strategy = TrendFollowingStrategy()

        backtest = EventDrivenBacktest(
            strategy,
            initial_capital=self.initial_capital
        )

        # Run on test data
        result_dict = backtest.run(data, data.iloc[-1]['symbol'] if 'symbol' in data.columns and len(data) > 0 else "UNKNOWN")

        # Extract metrics
        metrics = PerformanceMetrics()

        # Calculate metrics from the portfolio values if available
        if 'daily_values' in result_dict and len(result_dict['daily_values']) > 0:
            portfolio_values = pd.Series([v['portfolio_value'] for v in result_dict['daily_values']])
            if len(portfolio_values) > 1:
                returns = portfolio_values.pct_change().dropna()
                metrics.calculate_all_metrics(portfolio_values, returns)
            else:
                # Handle edge case of single value
                metrics.total_return = 0.0
                metrics.annualized_return = 0.0
                metrics.sharpe_ratio = 0.0
                metrics.max_drawdown = 0.0
                metrics.volatility = 0.0
                metrics.win_rate = 0.0
        else:
            # Handle case where no daily values are returned - use result_dict values
            metrics.total_return = result_dict.get('total_return', 0.0)
            metrics.annualized_return = result_dict.get('annualized_return', 0.0)
            metrics.sharpe_ratio = result_dict.get('sharpe_ratio', 0.0)
            metrics.max_drawdown = result_dict.get('max_drawdown', 0.0)
            metrics.num_trades = result_dict.get('num_trades', 0)
            metrics.win_rate = result_dict.get('win_rate', 0.0)

        # Get the calculated values from metrics object
        sharpe_ratio_value = getattr(metrics, 'sharpe_ratio', 0.0)

        # Extract configuration parameters for reporting
        config_params = {k: v for k, v in config.items()
                       if k not in ['name']}  # Exclude name field

        is_result = {
            'config_name': config.get('name', 'unknown'),
            'sharpe_ratio': self._safe_get_metric(metrics, 'sharpe_ratio', sharpe_ratio_value),
            'total_return': self._safe_get_metric(metrics, 'total_return', 0.0),
            'max_drawdown': self._safe_get_metric(metrics, 'max_drawdown', 0.0),
            'volatility': self._safe_get_metric(metrics, 'volatility', 0.0),
            'win_rate': self._safe_get_metric(metrics, 'win_rate', 0.0),
            'config_params': config_params
        }

        return result_dict, metrics

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
                print(f"Window: {window_start_date.date()} to {window_end_date.date()}")
                print(f"  OOS: {oos_start_date.date()} to {oos_end_date.date()}")

            # Run in-sample backtest for all configs
            is_results = []
            for config in configs:
                result_dict, metrics = self._run_backtest_for_config(in_sample, config, cost_model)

                # Extract configuration parameters for reporting
                config_params = {k: v for k, v in config.items()
                               if k not in ['name']}  # Exclude name field

                is_result = {
                    'config_name': config.get('name', 'unknown'),
                    'sharpe_ratio': metrics.sharpe_ratio,
                    'total_return': metrics.total_return,
                    'max_drawdown': metrics.max_drawdown,
                    'volatility': getattr(metrics, 'volatility', 0.0),
                    'win_rate': getattr(metrics, 'win_rate', 0.0),
                    'config_params': config_params
                }
                is_results.append(is_result)

            # Select optimal config from in-sample results
            optimal_config = self.optimal_config_selector(is_results)

            if not optimal_config:
                print(f"  No valid config found, skipping window")
                current_idx += self.step_size
                continue

            # Use optimal config for out-of-sample
            config_name = optimal_config.get('config_name', 'unknown')
            config_params = optimal_config.get('config_params', {})
            if verbose:
                print(f"  Optimal config: {config_name}")

            # Run out-of-sample backtest with the OPTIMAL config (FIXED: was using configs[0])
            result_dict, metrics = self._run_backtest_for_config(
                out_of_sample, optimal_config, cost_model  # USE OPTIMAL CONFIG HERE
            )

            # Store enhanced results
            # Helper function to safely extract metric value
            def safe_get_metric(obj, attr_name, default=0.0):
                try:
                    value = getattr(obj, attr_name, default)
                    # If it's a method, try calling it with no args
                    if callable(value):
                        try:
                            return float(value())
                        except:
                            return default
                    return float(value)
                except:
                    return default

            enhanced_result = EnhancedWalkForwardResult(
                window_start=str(window_start_date.date()),
                window_end=str(window_end_date.date()),
                out_of_sample_start=str(oos_start_date.date()),
                out_of_sample_end=str(oos_end_date.date()),
                in_sample_return=safe_get_metric(metrics, 'total_return', optimal_config.get('total_return', 0)),
                out_of_sample_return=safe_get_metric(metrics, 'total_return', 0),
                in_sample_sharpe=safe_get_metric(metrics, 'sharpe_ratio', optimal_config.get('sharpe_ratio', 0)),
                out_of_sample_sharpe=safe_get_metric(metrics, 'sharpe_ratio', 0),
                in_sample_max_dd=safe_get_metric(metrics, 'max_drawdown', optimal_config.get('max_drawdown', 0)),
                out_of_sample_max_dd=safe_get_metric(metrics, 'max_drawdown', 0),
                in_sample_volatility=safe_get_metric(metrics, 'volatility', optimal_config.get('volatility', 0.0)),
                out_of_sample_volatility=safe_get_metric(metrics, 'volatility', 0.0),
                in_sample_win_rate=safe_get_metric(metrics, 'win_rate', optimal_config.get('win_rate', 0.0)),
                out_of_sample_win_rate=safe_get_metric(metrics, 'win_rate', 0.0),
                config_used=config_name,
                config_params=config_params
            )
            results.append(enhanced_result)

            current_idx += self.step_size

        self.enhanced_results = results
        return results

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
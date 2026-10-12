#!/usr/bin/env python3
"""Run full research pipeline for strategy evaluation.

This script:
1. Downloads historical data
2. Runs backtests on train/val/test splits
3. Performs robustness testing
4. Generates research report
"""

import os
import sys
import yaml
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from trading_bot.data.downloader import DataDownloader
from trading_bot.data.validator import DataValidator
from trading_bot.strategies.trend_following import TrendFollowingStrategy
from trading_bot.backtesting.engine import EventDrivenBacktest
from trading_bot.backtesting.costs import TransactionCostModel
from trading_bot.backtesting.metrics import PerformanceMetrics
from trading_bot.backtesting.robustness import ParameterSensitivity, WhitesRealityCheck
from trading_bot.research.experiments import ExperimentRunner, load_grid_config
from trading_bot.research.walk_forward import WalkForwardAnalyzer
from trading_bot.research.reports import ResearchReportGenerator, StrategyPerformance

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('research')


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def run_research_pipeline(config_path: str = "config/config.yaml"):
    """Run the complete research pipeline.

    Args:
        config_path: Path to configuration file
    """
    # Load configuration
    config = load_config(config_path)
    logger.info(f"Loaded configuration from {config_path}")

    # Extract config values
    symbols = config.get('data', {}).get('symbols', ['AAPL'])
    symbol = symbols[0]  # Start with single symbol
    start_date = config.get('data', {}).get('start_date', '2010-01-01')
    end_date = config.get('data', {}).get('end_date', '2026-10-03')

    train_start = config.get('backtest', {}).get('train_start', '2015-01-01')
    train_end = config.get('backtest', {}).get('train_end', '2020-12-31')
    val_start = config.get('backtest', {}).get('val_start', '2021-01-01')
    val_end = config.get('backtest', {}).get('val_end', '2022-12-31')
    test_start = config.get('backtest', {}).get('test_start', '2023-01-01')
    test_end = config.get('backtest', {}).get('test_end', '2026-10-03')

    initial_capital = config.get('backtest', {}).get('initial_capital', 100000)

    # Create output directory
    output_dir = "research_outputs"
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Download data
    logger.info("=" * 60)
    logger.info("Step 1: Downloading historical data")
    logger.info("=" * 60)

    downloader = DataDownloader()
    data = downloader.download(symbol, start_date, end_date)

    logger.info(f"Downloaded {len(data)} rows of data for {symbol}")
    logger.info(f"Date range: {data['date'].min()} to {data['date'].max()}")

    # Step 2: Validate data
    logger.info("=" * 60)
    logger.info("Step 2: Validating data quality")
    logger.info("=" * 60)

    validator = DataValidator()
    validation_result = validator.validate(data)

    if not validation_result['valid']:
        logger.error(f"Data validation failed: {validation_result['errors']}")
        sys.exit(1)

    logger.info("Data validation passed")

    # Step 3: Load strategy grid
    logger.info("=" * 60)
    logger.info("Step 3: Loading strategy configuration grid")
    logger.info("=" * 60)

    # Load from strategy_params.yaml if it exists
    try:
        with open('config/strategy_params.yaml', 'r') as f:
            grid_config = yaml.safe_load(f)
    except FileNotFoundError:
        # Default grid
        grid_config = {
            'ma_pairs': [[20, 50], [30, 100], [50, 150], [50, 200]],
            'entry_thresholds': [0.3, 0.4, 0.5, 0.6, 0.7],
            'exit_thresholds': [-0.5, -0.4, -0.3, -0.2, -0.1]
        }

    # Generate config combinations
    configs = []
    counter = 1
    for ma_pair in grid_config.get('ma_pairs', [[20, 50]]):
        for entry_th in grid_config.get('entry_thresholds', [0.5]):
            for exit_th in grid_config.get('exit_thresholds', [-0.3]):
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

    logger.info(f"Generated {len(configs)} strategy configurations")

    # Step 4: Split data chronologically
    logger.info("=" * 60)
    logger.info("Step 4: Splitting data chronologically")
    logger.info("=" * 60)

    train_data = data[
        (data['date'] >= pd.Timestamp(train_start)) &
        (data['date'] <= pd.Timestamp(train_end))
    ]
    val_data = data[
        (data['date'] >= pd.Timestamp(val_start)) &
        (data['date'] <= pd.Timestamp(val_end))
    ]
    test_data = data[
        (data['date'] >= pd.Timestamp(test_start)) &
        (data['date'] <= pd.Timestamp(test_end))
    ]

    logger.info(f"Train: {train_start} to {train_end} ({len(train_data)} days)")
    logger.info(f"Val:   {val_start} to {val_end} ({len(val_data)} days)")
    logger.info(f"Test:  {test_start} to {test_end} ({len(test_data)} days)")

    # Step 5: Run parameter sensitivity analysis on training data
    logger.info("=" * 60)
    logger.info("Step 5: Running parameter sensitivity analysis")
    logger.info("=" * 60)

    sensitivity = ParameterSensitivity(train_data, symbol, initial_capital)

    # Test MA pairs
    ma_results = sensitivity.test_ma_pairs(
        ma_pairs=[c['strategy']['short_window']/c['strategy']['medium_window'] for c in configs[:10]],
        entry_threshold=0.5,
        exit_threshold=-0.3
    )

    logger.info(f"MA pair testing complete: {len(ma_results)} configurations tested")

    # Step 6: Run full experiment on validation data
    logger.info("=" * 60)
    logger.info("Step 6: Running full experiment on validation data")
    logger.info("=" * 60)

    cost_model = TransactionCostModel(
        commission=config.get('costs', {}).get('commission', 0.0),
        slippage_bps=config.get('costs', {}).get('slippage_bps', 5.0),
        bid_ask_spread_bps=config.get('costs', {}).get('bid_ask_spread_bps', 2.0)
    )

    runner = ExperimentRunner(data, symbol, output_dir)
    val_results = runner.run_configuration_grid(grid_config, train_data, val_data)

    # Find best configurations
    best_configs = runner.find_best_configs(val_results)

    logger.info(f"Found {len(best_configs)} robust configurations")
    for i, config in enumerate(best_configs, 1):
        logger.info(f"  {i}. {config.config_name}: "
                   f"Sharpe={config.sharpe_ratio:.2f}, "
                   f"Return={config.total_return:.1%}")

    # Step 7: Run White's Reality Check
    logger.info("=" * 60)
    logger.info("Step 7: Running White's Reality Check")
    logger.info("=" * 60)

    # Collect returns for White's test
    strategy_returns = [r.total_return for r in val_results]
    benchmark_return = 0.0  # Cash return

    reality_check = WhitesRealityCheck(n_bouts=1000)
    white_results = reality_check.reality_check_test(strategy_returns, benchmark_return)

    logger.info(f"White's Reality Check:")
    logger.info(f"  P-value: {white_results['p_value']:.4f}")
    logger.info(f"  Adjusted P-value: {white_results['adjusted_p_value']:.4f}")
    logger.info(f"  Has Edge: {white_results['has_edge']}")

    # Step 8: Run walk-forward analysis on test data
    logger.info("=" * 60)
    logger.info("Step 8: Running walk-forward analysis on test data")
    logger.info("=" * 60)

    analyzer = WalkForwardAnalyzer(test_data, symbol, initial_capital)
    walk_results = analyzer.run_analysis(best_configs[:3], cost_model)

    summary = analyzer.calculate_summary_stats()
    logger.info(f"Walk-forward summary:")
    logger.info(f"  Windows: {summary.get('num_windows', 0)}")
    logger.info(f"  Avg IS Return: {summary.get('avg_is_return', 0):.1%}")
    logger.info(f"  Avg OOS Return: {summary.get('avg_oos_return', 0):.1%}")

    # Step 9: Generate research report
    logger.info("=" * 60)
    logger.info("Step 9: Generating research report")
    logger.info("=" * 60)

    generator = ResearchReportGenerator(output_dir)

    # Add performance data
    for result in val_results:
        generator.add_performance_data(StrategyPerformance(
            config_name=result.config_name,
            total_return=result.total_return,
            annualized_return=result.annualized_return,
            annualized_volatility=result.annualized_volatility,
            sharpe_ratio=result.sharpe_ratio,
            sortino_ratio=result.sortino_ratio,
            max_drawdown=result.max_drawdown,
            win_rate=result.win_rate,
            profit_factor=result.profit_factor,
            num_trades=result.num_trades,
            buy_and_hold_return=result.buy_and_hold_return,
            excess_return=result.excess_return
        ))

    # Add robustness results
    generator.add_robustness_results(white_results)

    # Add walk-forward results
    generator.add_walk_forward_results(walk_results)

    # Save report
    report_path = f"{output_dir}/research_report_{symbol}_{datetime.now().strftime('%Y%m%d')}.md"
    generator.save_report(report_path)

    logger.info(f"Research report saved to {report_path}")

    # Print final verdict
    logger.info("=" * 60)
    logger.info("FINAL VERDICT")
    logger.info("=" * 60)

    avg_sharpe = sum(r.sharpe_ratio for r in val_results) / len(val_results)
    has_edge = white_results['has_edge']

    if not has_edge or avg_sharpe < 0:
        verdict = "REJECT - No evidence of predictive edge"
    elif avg_sharpe < 0.5:
        verdict = "WEAK - Some evidence but not robust"
    elif avg_sharpe < 1.0:
        verdict = "PROMISING - Good evidence, needs extended paper trading"
    else:
        verdict = "ROBUST - Strong evidence, ready for live trading"

    logger.info(f"Verdict: {verdict}")
    logger.info(f"Average Sharpe: {avg_sharpe:.2f}")
    logger.info(f"White's Reality Check (p-value): {white_results['p_value']:.4f}")

    return {
        'results': val_results,
        'white_results': white_results,
        'best_configs': best_configs,
        'walk_results': walk_results
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Run trading strategy research')
    parser.add_argument('--config', default='config/config.yaml',
                       help='Path to configuration file')

    args = parser.parse_args()

    results = run_research_pipeline(args.config)
    logger.info("Research pipeline complete")

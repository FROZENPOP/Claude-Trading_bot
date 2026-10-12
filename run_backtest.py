#!/usr/bin/env python3
"""Run a single backtest for strategy evaluation.

Usage:
    python run_backtest.py --symbol AAPL --strategy ma_crossover --train-start 2015-01-01 --train-end 2020-12-31
"""

import os
import sys
import yaml
import argparse
import logging
from datetime import datetime
from pathlib import Path
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from trading_bot.data.downloader import DataDownloader
from trading_bot.data.validator import DataValidator
from trading_bot.backtesting.engine import EventDrivenBacktest
from trading_bot.backtesting.costs import TransactionCostModel
from trading_bot.backtesting.metrics import PerformanceMetrics

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('backtest')


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def get_strategy_class(strategy_name: str):
    """Dynamically load strategy class by name.

    Args:
        strategy_name: Name of the strategy (e.g., 'trend_following', 'covered_call')

    Returns:
        Strategy class

    Raises:
        ValueError: If strategy name is not recognized
    """
    strategy_map = {
        'trend_following': ('trading_bot.strategies.trend_following', 'TrendFollowingStrategy'),
        'composite_score': ('trading_bot.strategies.composite_score', 'CompositeTrendScore'),
        'covered_call': ('trading_bot.strategies.covered_call', 'CoveredCallStrategy'),
        'cash_secured_put': ('trading_bot.strategies.covered_call', 'CashSecuredPutStrategy'),
        'iron_condor': ('trading_bot.strategies.iron_condor', 'IronCondorStrategy'),
        'vertical_spread': ('trading_bot.strategies.vertical_spread', 'VerticalSpreadStrategy'),
        'calendar_spread': ('trading_bot.strategies.calendar_spread', 'CalendarSpreadStrategy'),
    }

    if strategy_name not in strategy_map:
        raise ValueError(f"Unknown strategy: {strategy_name}. Available strategies: {list(strategy_map.keys())}")

    module_path, class_name = strategy_map[strategy_name]
    module = __import__(module_path, fromlist=[class_name])
    return getattr(module, class_name)


def run_single_backtest(
    symbol: str,
    data_start: str,
    data_end: str,
    train_start: str,
    train_end: str,
    initial_capital: float = 100000,
    commission: float = 0.0,
    slippage_bps: float = 5.0,
    bid_ask_spread_bps: float = 2.0,
    entry_threshold: float = 0.5,
    exit_threshold: float = -0.3,
    short_window: int = 20,
    medium_window: int = 50,
    long_window: int = 200,
    output_dir: str = "backtest_outputs",
    strategy_class=None
):
    """Run a single backtest.

    Args:
        symbol: Stock symbol
        data_start: Data start date
        data_end: Data end date
        train_start: Training period start
        train_end: Training period end
        initial_capital: Initial capital
        commission: Commission per trade
        slippage_bps: Slippage in basis points
        bid_ask_spread_bps: Bid-ask spread in basis points
        entry_threshold: Entry signal threshold
        exit_threshold: Exit signal threshold
        short_window: Short MA window
        medium_window: Medium MA window
        long_window: Long MA window
        output_dir: Output directory
        strategy_class: Strategy class to use (if None, defaults to TrendFollowingStrategy)

    Returns:
        Backtest results dictionary
    """
    logger.info(f"Starting backtest for {symbol}")
    logger.info(f"Period: {train_start} to {train_end}")
    logger.info(f"Initial capital: ${initial_capital:,.2f}")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Download data
    logger.info("Downloading data...")
    downloader = DataDownloader()
    data = downloader.download(symbol, data_start, data_end)

    logger.info(f"Downloaded {len(data)} rows")

    # Validate data
    validator = DataValidator()
    validation_passed = validator.validate(data)

    if not validation_passed:
        logger.error(f"Validation failed: {validator.errors}")
        return None

    # Filter to training period
    # Handle timezone-aware dates in data
    train_start_ts = pd.Timestamp(train_start, tz=data['date'].dt.tz)
    train_end_ts = pd.Timestamp(train_end, tz=data['date'].dt.tz)
    train_data = data[
        (data['date'] >= train_start_ts) &
        (data['date'] <= train_end_ts)
    ].copy()

    logger.info(f"Training data: {len(train_data)} days")

    # Create cost model
    cost_model = TransactionCostModel(
        commission=commission,
        slippage_bps=slippage_bps,
        bid_ask_spread_bps=bid_ask_spread_bps
    )

    # Create strategy
    if strategy_class is None:
        # Default to TrendFollowingStrategy for backward compatibility
        strategy_class = get_strategy_class('trend_following')

    # Handle different strategy types and their parameters
    strategy_name = strategy_class.__name__
    if strategy_name in ['TrendFollowingStrategy']:
        # Traditional MA strategies
        strategy = strategy_class(
            entry_threshold=entry_threshold,
            exit_threshold=exit_threshold,
            short_window=short_window,
            medium_window=medium_window,
            long_window=long_window
        )
        logger.info(f"Strategy: MA({short_window}/{medium_window}/{long_window})")
        logger.info(f"Thresholds: entry={entry_threshold}, exit={exit_threshold}")
    elif strategy_name == 'CompositeTrendScore':
        # Composite trend score uses entry/exit thresholds but MA params in methods
        strategy = strategy_class(
            entry_threshold=entry_threshold,
            exit_threshold=exit_threshold
        )
        logger.info(f"Strategy: CompositeTrendScore")
        logger.info(f"Thresholds: entry={entry_threshold}, exit={exit_threshold}")
    elif strategy_name in ['CoveredCallStrategy', 'CashSecuredPutStrategy']:
        # Option selling strategies - these don't use entry/exit thresholds in constructor
        strategy = strategy_class(
            underlying_symbol=symbol
        )
        logger.info(f"Strategy: {strategy_name}")
        logger.info("Using default parameters for option strategy")
    elif strategy_name in ['IronCondorStrategy', 'VerticalSpreadStrategy', 'CalendarSpreadStrategy']:
        # Option spread strategies - these don't use entry/exit thresholds in constructor
        strategy = strategy_class(
            underlying_symbol=symbol
        )
        logger.info(f"Strategy: {strategy_name}")
        logger.info("Using default parameters for option strategy")
    else:
        # Fallback for any other strategy - try common parameters
        try:
            strategy = strategy_class(
                underlying_symbol=symbol
            )
        except TypeError:
            try:
                strategy = strategy_class(
                    entry_threshold=entry_threshold,
                    exit_threshold=exit_threshold
                )
            except TypeError:
                try:
                    strategy = strategy_class(
                        entry_threshold=entry_threshold,
                        exit_threshold=exit_threshold,
                        short_window=short_window,
                        medium_window=medium_window,
                        long_window=long_window
                    )
                except TypeError:
                    # Last resort - try no arguments
                    strategy = strategy_class()
        logger.info(f"Strategy: {strategy_name}")

    # Run backtest
    logger.info("Running backtest...")
    backtest = EventDrivenBacktest(
        strategy=strategy,
        initial_capital=initial_capital,
        cost_model=cost_model
    )

    results = backtest.run(train_data, symbol)

    # Calculate metrics
    portfolio_values = pd.Series(
        [v['portfolio_value'] for v in results['daily_values']]
    )
    benchmark_values = (
        train_data['adjusted_close'] /
        train_data['adjusted_close'].iloc[0] * initial_capital
    )

    metrics = PerformanceMetrics()
    perf_metrics = metrics.calculate_all_metrics(portfolio_values, benchmark_values)

    # Add additional metrics
    results['metrics'] = perf_metrics
    # Note: num_trades, win_rate, and profit_factor are already calculated by the engine

    # Save results
    # Create a generic strategy identifier for the filename
    strategy_name_lower = strategy_class.__name__.lower().replace('strategy', '')
    results_file = (
        f"{output_dir}/{symbol}_"
        f"{strategy_name_lower}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
    )

    # Convert to serializable format
    serializable_results = {
        'symbol': symbol,
        'period': {'start': train_start, 'end': train_end},
        'parameters': {
            'initial_capital': initial_capital,
            'commission': commission,
            'slippage_bps': slippage_bps,
            'bid_ask_spread_bps': bid_ask_spread_bps,
            'entry_threshold': entry_threshold,
            'exit_threshold': exit_threshold,
            'strategy': strategy_class.__name__
        },
        'metrics': perf_metrics,
        'num_trades': results['num_trades'],
        'win_rate': results['win_rate'],
        'profit_factor': results['profit_factor'],
        'buy_and_hold_return': results.get('buy_and_hold_return', 0),
        'excess_return': results.get('excess_return', 0),
        'trades': len(results.get('trades', [])),
        'daily_values': results['daily_values'][:100],  # First 100 days
        'summary': {
            'start_value': results['daily_values'][0]['portfolio_value'],
            'end_value': results['daily_values'][-1]['portfolio_value'],
            'total_return': perf_metrics.get('total_return', 0),
            'annualized_return': perf_metrics.get('annualized_return', 0),
            'sharpe_ratio': perf_metrics.get('sharpe_ratio', 0),
            'max_drawdown': perf_metrics.get('max_drawdown', 0)
        }
    }

    with open(results_file, 'w') as f:
        yaml.dump(serializable_results, f, default_flow_style=False)

    logger.info(f"Results saved to {results_file}")

    # Print summary
    print("\n" + "=" * 60)
    print(f"BACKTEST RESULTS: {symbol}")
    print("=" * 60)
    print(f"Period: {train_start} to {train_end}")
    print(f"Initial Capital: ${initial_capital:,.2f}")
    print("-" * 40)
    print(f"Total Return:        {perf_metrics.get('total_return', 0):.1%}")
    print(f"Annualized Return:   {perf_metrics.get('annualized_return', 0):.1%}")
    print(f"Sharpe Ratio:        {perf_metrics.get('sharpe_ratio', 0):.2f}")
    print(f"Sortino Ratio:       {perf_metrics.get('sortino_ratio', 0):.2f}")
    print(f"Max Drawdown:        {perf_metrics.get('max_drawdown', 0):.1%}")
    print(f"Annualized Vol:      {perf_metrics.get('annualized_volatility', 0):.1%}")
    print("-" * 40)
    print(f"Num Trades:          {results['num_trades']}")
    print(f"Win Rate:            {results['win_rate']:.1%}")
    print(f"Profit Factor:       {results['profit_factor']:.2f}")
    print(f"Buy & Hold Return:   {results.get('buy_and_hold_return', 0):.1%}")
    print(f"Excess Return:       {results.get('excess_return', 0):.1%}")
    print("=" * 60)

    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Run a single strategy backtest'
    )

    # Data parameters
    parser.add_argument('--symbol', default='AAPL',
                       help='Stock symbol (default: AAPL)')
    parser.add_argument('--data-start', default='2010-01-01',
                       help='Data start date (default: 2010-01-01)')
    parser.add_argument('--data-end', default='2026-10-03',
                       help='Data end date (default: 2026-10-03)')

    # Period parameters
    parser.add_argument('--train-start', default='2015-01-01',
                       help='Training period start (default: 2015-01-01)')
    parser.add_argument('--train-end', default='2020-12-31',
                       help='Training period end (default: 2020-12-31)')

    # Strategy parameters
    parser.add_argument('--entry-threshold', type=float, default=0.5,
                       help='Entry threshold (default: 0.5)')
    parser.add_argument('--exit-threshold', type=float, default=-0.3,
                       help='Exit threshold (default: -0.3)')
    parser.add_argument('--short-window', type=int, default=20,
                       help='Short MA window (default: 20)')
    parser.add_argument('--medium-window', type=int, default=50,
                       help='Medium MA window (default: 50)')
    parser.add_argument('--long-window', type=int, default=200,
                       help='Long MA window (default: 200)')

    # Financial parameters
    parser.add_argument('--initial-capital', type=float, default=100000,
                       help='Initial capital (default: 100000)')
    parser.add_argument('--commission', type=float, default=0.0,
                       help='Commission per trade (default: 0)')
    parser.add_argument('--slippage-bps', type=float, default=5.0,
                       help='Slippage in basis points (default: 5)')
    parser.add_argument('--bid-ask-bps', type=float, default=2.0,
                       help='Bid-ask spread in basis points (default: 2)')

    # Strategy parameters
    parser.add_argument('--strategy', type=str, default='trend_following',
                       help='Strategy to use (default: trend_following). Available: trend_following, composite_score, covered_call, cash_secured_put, iron_condor, vertical_spread, calendar_spread')

    parser.add_argument('--output-dir', default='backtest_outputs',
                       help='Output directory (default: backtest_outputs)')

    args = parser.parse_args()

    # Get strategy class
    try:
        strategy_class = get_strategy_class(args.strategy)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    results = run_single_backtest(
        symbol=args.symbol,
        data_start=args.data_start,
        data_end=args.data_end,
        train_start=args.train_start,
        train_end=args.train_end,
        initial_capital=args.initial_capital,
        commission=args.commission,
        slippage_bps=args.slippage_bps,
        bid_ask_spread_bps=args.bid_ask_bps,
        entry_threshold=args.entry_threshold,
        exit_threshold=args.exit_threshold,
        short_window=args.short_window,
        medium_window=args.medium_window,
        long_window=args.long_window,
        output_dir=args.output_dir,
        strategy_class=strategy_class
    )

    if results:
        logger.info("Backtest complete")
    else:
        logger.error("Backtest failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

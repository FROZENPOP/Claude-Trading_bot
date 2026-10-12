#!/usr/bin/env python3
"""
Run only the research portion of options strategy research to generate final report.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from research_options_strategies import (
    OptionsDataPipeline,
    SignalGenerator,
    OptionsBacktester,
    run_robustness_testing,
    validate_strategy_edge
)
from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy
from trading_bot.strategies.covered_call import CoveredCallStrategy, CashSecuredPutStrategy

def run_strategy_backtest(strategy, lookback_start, end_date, symbol, initial_capital=100000.0):
    """Run backtest for a given strategy."""
    # Initialize components
    pipeline = OptionsDataPipeline(symbol=symbol)
    signal_generator = SignalGenerator()
    backtester = OptionsBacktester(initial_capital=initial_capital, symbol=symbol)

    # Run backtest
    results = backtester.run_strategy_backtest(strategy, lookback_start, end_date)

    return results

def main():
    """Run research strategies and generate report."""
    print("Running options strategy research to generate final report...")
    print("=" * 60)

    # Define strategies to test
    strategies = [
        ('Vertical Spread', VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)),
        ('Covered Call', CoveredCallStrategy('AAPL', max_position_size=0.02)),
        ('Cash Secured Put', CashSecuredPutStrategy('AAPL', max_position_size=0.02))
    ]

    # Define analysis parameters
    lookback_start = "2026-07-19"
    end_date = "2026-09-07"
    symbol = "AAPL"

    results = {}

    for name, strategy in strategies:
        print(f"\nTesting {name} strategy...")
        try:
            # Run backtest
            backtest_result = run_strategy_backtest(
                strategy=strategy,
                lookback_start=lookback_start,
                end_date=end_date,
                symbol=symbol,
                initial_capital=100000.0
            )

            # Run robustness testing
            robustness_result = run_robustness_testing(
                strategy=strategy,
                backtest_results=backtest_result,
                lookback_start=lookback_start,
                end_date=end_date,
                symbol=symbol
            )

            results[name] = {
                'backtest': backtest_result,
                'robustness': robustness_result
            }

            print(f"  ✓ {name} completed")
            print(f"    Total Return: {backtest_result.get('total_return', 0):.2%}")
            print(f"    Sharpe Ratio: {backtest_result.get('sharpe_ratio', 0):.3f}")
            print(f"    Max Drawdown: {backtest_result.get('max_drawdown', 0):.2%}")

        except Exception as e:
            print(f"  ✗ {name} failed: {e}")
            results[name] = {'error': str(e)}

    # Generate summary report
    print("\n" + "=" * 60)
    print("FINAL RESEARCH REPORT")
    print("=" * 60)

    for name, result in results.items():
        print(f"\n{name} Strategy:")
        if 'error' in result:
            print(f"  ERROR: {result['error']}")
        else:
            backtest = result['backtest']
            robustness = result['robustness']
            print(f"  Period: {lookback_start} to {end_date}")
            print(f"  Total Return: {backtest.get('total_return', 0):.2%}")
            print(f"  Annualized Return: {backtest.get('annualized_return', 0):.2%}")
            print(f"  Sharpe Ratio: {backtest.get('sharpe_ratio', 0):.3f}")
            print(f"  Max Drawdown: {backtest.get('max_drawdown', 0):.2%}")
            # Calculate win rate if we have the data
            num_trades = backtest.get('num_trades', 0)
            completed_trades = backtest.get('completed_trades', 0)
            if num_trades > 0:
                win_rate = completed_trades / num_trades
                print(f"  Win Rate: {win_rate:.2%}")
            else:
                print(f"  Win Rate: N/A")
            print(f"  Total Trades: {num_trades}")

            if 'robustness_metrics' in robustness:
                print(f"  Robustness Score: {robustness['robustness_metrics'].get('overall_score', 0):.3f}")

    print("\n" + "=" * 60)
    print("Research report generation complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
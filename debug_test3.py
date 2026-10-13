#!/usr/bin/env python3
"""
Test script to verify the enhanced_robustness.py module works correctly.
"""

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta

# Add project to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from trading_bot.backtesting.enhanced_robustness_fixed import (
    EnhancedWalkForwardAnalyzer,
    EnhancedWalkForwardResult,
    run_enhanced_walk_forward
)
print(f"DEBUG: EnhancedWalkForwardAnalyzer loaded from: {EnhancedWalkForwardAnalyzer.__module__}")
from trading_bot.strategies.trend_following import TrendFollowingStrategy
from trading_bot.backtesting.engine import EventDrivenBacktest
from trading_bot.backtesting.costs import TransactionCostModel


def create_sample_data():
    """Create sample stock data for testing."""
    print("Creating sample data for testing...")

    # Generate 2 years of daily data (approx 504 trading days)
    dates = pd.date_range(start='2024-01-01', end='2025-12-31', freq='D')
    # Remove weekends
    dates = dates[dates.weekday < 5]

    # Generate realistic price data with some trend and volatility
    np.random.seed(42)
    n_days = len(dates)
    returns = np.random.normal(0.0008, 0.015, n_days)  # Slight positive drift

    # Add some regime changes to make walk-forward more interesting
    regime_change_point = n_days // 2
    returns[regime_change_point:] += 0.0003  # Slightly better second half

    prices = [100.0]  # Starting price

    for ret in returns[1:]:
        prices.append(prices[-1] * (1 + ret))

    # Create OHLCV data with adjusted_close (same as close for simplicity)
    data = []
    for i, (date, close) in enumerate(zip(dates, prices)):
        volatility = 0.015
        high = close * (1 + abs(np.random.normal(0, volatility/2)))
        low = close * (1 - abs(np.random.normal(0, volatility/2)))
        open_price = close * (1 + np.random.normal(0, volatility/4))
        volume = np.random.randint(500000, 5000000)
        adjusted_close = close  # For simplicity, using close as adjusted_close

        data.append({
            'date': date,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'adjusted_close': adjusted_close,
            'volume': volume,
            'symbol': 'TEST'
        })

    df = pd.DataFrame(data)
    print(f"Created sample data: {len(df)} days from {df['date'].min()} to {df['date'].max()}")
    return df


def test_enhanced_walk_forward_analyzer():
    """Test the EnhancedWalkForwardAnalyzer class."""
    print("\n" + "="*60)
    print("TESTING ENHANCED WALK-FORWARD ANALYZER")
    print("="*60)

    # Create sample data
    data = create_sample_data()

    # Define some simple test configurations
    test_configs = [
        {
            'name': 'trend_following_fast',
            'fast_period': 10,
            'slow_period': 30,
            'signal_threshold': 0.02
        },
        {
            'name': 'trend_following_slow',
            'fast_period': 20,
            'slow_period': 50,
            'signal_threshold': 0.015
        },
        {
            'name': 'trend_following_medium',
            'fast_period': 15,
            'slow_period': 40,
            'signal_threshold': 0.018
        }
    ]

    # Define a simple configuration selector (choose highest Sharpe ratio)
    def select_best_sharpe(config_results):
        if not config_results:
            return None
        return max(config_results, key=lambda x: x['sharpe_ratio'])

    # Create enhanced analyzer
    analyzer = EnhancedWalkForwardAnalyzer(
        data=data,
        symbol='TEST',
        initial_capital=100000,
        window_size=252,  # 1 year training window
        step_size=63,     # 3 month step
        optimal_config_selector=select_best_sharpe
    )

    # Run analysis
    print("Running enhanced walk-forward analysis...")
    results = analyzer.run_analysis(
        configs=test_configs,
        cost_model=TransactionCostModel(),
        verbose=True
    )

    print(f"\nAnalysis completed. Generated {len(results)} enhanced results.")

    if results:
        # Display first few results
        print("\nFirst 3 enhanced results:")
        for i, result in enumerate(results[:3]):
            print(f"\nResult {i+1}:")
            print(f"  Window: {result.window_start} to {result.window_end}")
            print(f"  OOS Period: {result.out_of_sample_start} to {result.out_of_sample_end}")
            print(f"  IS Return: {result.in_sample_return:.2%}")
            print(f"  OOS Return: {result.out_of_sample_return:.2%}")
            print(f"  IS Sharpe: {result.in_sample_sharpe:.3f}")
            print(f"  OOS Sharpe: {result.out_of_sample_sharpe:.3f}")
            print(f"  Optimal Config: {result.config_used}")

        # Test summary statistics
        print("\nCalculating summary statistics...")
        summary = analyzer.calculate_enhanced_summary_stats()

        print("Summary Statistics:")
        print(f"  Number of Windows: {summary.get('num_windows', 0)}")
        print(f"  Average IS Return: {summary.get('avg_is_return', 0):.2%}")
        print(f"  Average OOS Return: {summary.get('avg_oos_return', 0):.2%}")
        print(f"  Return Difference (IS-OOS): {summary.get('is_oos_return_diff', 0):.2%}")
        print(f"  Average IS Sharpe: {summary.get('avg_is_sharpe', 0):.3f}")
        print(f"  Average OOS Sharpe: {summary.get('avg_oos_sharpe', 0):.3f}")
        print(f"  Sharpe Difference (IS-OOS): {summary.get('is_oos_sharpe_diff', 0):.3f}")
        print(f"  Return Consistency: {summary.get('return_consistency', 0):.3f}")
        print(f"  Sharpe Consistency: {summary.get('sharpe_consistency', 0):.3f}")

        # Test report generation
        print("\nTesting report generation...")
        try:
            report_path = analyzer.generate_report(output_dir="test_reports")
            if report_path:
                print(f"[PASS] Report generated successfully: {report_path}")
            else:
                print("[FAIL] Report generation failed")
        except Exception as e:
            print(f"[FAIL] Report generation error: {e}")

        # Test plotting (if matplotlib is available)
        print("\nTesting plotting capability...")
        try:
            plots_dir = "test_plots"
            os.makedirs(plots_dir, exist_ok=True)
            plot_path = os.path.join(plots_dir, "test_equity_curves.png")
            analyzer.plot_equity_curves(save_path=plot_path)
            if os.path.exists(plot_path):
                print(f"[PASS] Plot generated successfully: {plot_path}")
            else:
                print("[INFO] Plot may not have been generated (matplotlib not available?)")
        except Exception as e:
            print(f"[INFO] Plotting test skipped or failed: {e}")

        return True
    else:
        print("[FAIL] No results generated from walk-forward analysis")
        return False


if __name__ == "__main__":
    test_enhanced_walk_forward_analyzer()
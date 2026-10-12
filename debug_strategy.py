#!/usr/bin/env python3
"""Debug what the strategy's generate_spread_signals method is returning."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add project to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from research_options_strategies import OptionsDataPipeline
from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy

def debug_strategy_signals():
    """Debug what the strategy's generate_spread_signals method returns."""
    print("DEBUGGING STRATEGY GENERATE_SPREAD_SIGNALS METHOD")
    print("=" * 60)

    # Use the same pipeline as in the diagnostic backtest
    pipeline = OptionsDataPipeline(symbol="AAPL")

    # Test the same scenario as diagnostic backtest day 1
    lookback_start = "2026-07-13"
    end_date = "2026-09-01"

    print(f"Fetching stock data from {lookback_start} to {end_date}")

    stock_data = pipeline.get_stock_data(lookback_start, end_date)

    if not stock_data.empty:
        current_date = stock_data['date'].iloc[-1]
        available_data = stock_data[stock_data['date'] <= current_date].copy()

        print(f"Stock data shape: {stock_data.shape}")
        print(f"Current date: {current_date}")
        print(f"Available data points: {len(available_data)}")

        # Get option chain
        option_chain = pipeline.get_option_chain_data(end_date)
        print(f"Option chain size: {len(option_chain)} contracts")

        # Create strategy
        strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)

        # Call the method that diagnostic backtest calls
        print("\nCalling strategy.generate_spread_signals...")
        signals = strategy.generate_spread_signals(available_data, option_chain, current_date)

        print(f"Number of spread signals generated: {len(signals)}")

        if len(signals) > 0:
            print("Spread signals:")
            for i, signal in enumerate(signals[:3]):  # Show first 3
                print(f"  Signal {i+1}:")
                print(f"    Type: {getattr(signal, 'signal_type', 'unknown')}")
                print(f"    Strength: {getattr(signal, 'signal_strength', 0.0):.3f}")
                if hasattr(signal, 'long_strike'):
                    print(f"    Long strike: {signal.long_strike}")
                if hasattr(signal, 'short_strike'):
                    print(f"    Short strike: {signal.short_strike}")
                if hasattr(signal, 'net_debit'):
                    print(f"    Net debit: ${signal.net_debit:.2f}")
        else:
            print("No spread signals generated")
            print("Let's check what signal the signal generator produced...")

            # Import signal generator and see what it produces
            from trading_bot.strategies.signals import SignalGenerator
            signal_generator = SignalGenerator()
            raw_signal = signal_generator.get_signal(available_data, current_date)

            if raw_signal is not None:
                print(f"Raw signal from signal generator: {raw_signal.signal_type} (strength: {raw_signal.signal_strength:.3f})")
                print(f"  Details: {raw_signal.metadata.get('details', 'No details')}")

                # Check if it meets strategy thresholds
                print(f"\nStrategy thresholds:")
                print(f"  Min signal strength: {getattr(strategy, 'min_signal_strength', 'Not found')}")
                print(f"  Requires bullish/bearish: {raw_signal.signal_type in ['bullish', 'bearish']}")
                if hasattr(strategy, 'min_signal_strength'):
                    meets_threshold = raw_signal.signal_strength >= strategy.min_signal_strength
                    print(f"  Meets strength threshold ({strategy.min_signal_strength}): {meets_threshold}")
            else:
                print("Raw signal from signal generator: None")

def test_multiple_days_like_backtest():
    """Test multiple days like the diagnostic backtest does."""
    print("\n" + "=" * 60)
    print("TESTING MULTIPLE DAYS LIKE DIAGNOSTIC BACKTEST")
    print("=" * 60)

    pipeline = OptionsDataPipeline(symbol="AAPL")
    strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)

    # Test the same dates as in the diagnostic backtest output
    test_dates = [
        "2026-09-01",
        "2026-09-02",
        "2026-09-07",
        "2026-09-08",
        "2026-09-09"
    ]

    total_spread_signals = 0
    total_raw_signals = 0

    from trading_bot.strategies.signals import SignalGenerator
    signal_generator = SignalGenerator()

    for date_str in test_dates:
        print(f"\n--- Testing {date_str} ---")

        # Get lookback data (50 days before like diagnostic backtest)
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        lookback_start = (dt - timedelta(days=50)).strftime('%Y-%m-%d')

        stock_data = pipeline.get_stock_data(lookback_start, date_str)

        if not stock_data.empty:
            current_date = stock_data['date'].iloc[-1]
            available_data = stock_data[stock_data['date'] <= current_date].copy()

            # Get raw signal
            raw_signal = signal_generator.get_signal(available_data, current_date)
            if raw_signal is not None:
                total_raw_signals += 1
                print(f"Raw signal: {raw_signal.signal_type} (strength: {raw_signal.signal_strength:.3f})")

                # Get option chain
                option_chain = pipeline.get_option_chain_data(date_str)

                # Get spread signals from strategy
                spread_signals = strategy.generate_spread_signals(available_data, option_chain, current_date)
                spread_count = len(spread_signals)
                total_spread_signals += spread_count
                print(f"Spread signals: {spread_count}")

                if spread_count > 0:
                    for signal in spread_signals:
                        print(f"  {getattr(signal, 'signal_type', '?')} {getattr(signal, 'signal_strength', 0.0):.3f} "
                              f"({getattr(signal, 'long_strike', 0.0)}/{getattr(signal, 'short_strike', 0.0)})")
            else:
                print("Raw signal: None")
        else:
            print("No stock data")

    print(f"\nSUMMARY:")
    print(f"  Raw signals generated: {total_raw_signals}")
    print(f"  Spread signals generated: {total_spread_signals}")

def main():
    """Main debug function."""
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    debug_strategy_signals()
    test_multiple_days_like_backtest()

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
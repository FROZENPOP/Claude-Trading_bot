#!/usr/bin/env python3
"""Test that the fix works correctly."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add project to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from research_options_strategies import OptionsDataPipeline
from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy
from trading_bot.strategies.signals import SignalGenerator

def test_fix():
    """Test that the fix allows spread signals to be generated."""
    print("TESTING THE FIX FOR VERTICAL SPREAD STRATEGY")
    print("=" * 55)

    # Create test data
    pipeline = OptionsDataPipeline(symbol="AAPL")
    signal_generator = SignalGenerator()

    # Use the same date that showed the bearish signal in our earlier debug
    lookback_start = "2026-07-19"
    end_date = "2026-09-07"

    print(f"Loading data from {lookback_start} to {end_date}")

    stock_data = pipeline.get_stock_data(lookback_start, end_date)

    if stock_data.empty:
        print("ERROR: No stock data loaded")
        return False

    current_date = stock_data['date'].iloc[-1]
    available_data = stock_data[stock_data['date'] <= current_date].copy()
    option_chain = pipeline.get_option_chain_data(end_date)

    print(f"Stock data: {len(available_data)} rows")
    print(f"Option chain: {len(option_chain)} contracts")
    print(f"Current date: {current_date}")

    # Test signal generation first
    print("\n--- Testing Signal Generation ---")
    raw_signal = signal_generator.get_signal(available_data, current_date)

    if raw_signal is None:
        print("ERROR: No signal generated")
        return False

    print(f"Raw signal: {raw_signal.signal_type} (strength: {raw_signal.signal_strength:.3f})")
    print(f"  Details: {raw_signal.metadata.get('details', 'No details')}")

    # Test the strategy's spread signal generation
    print("\n--- Testing Strategy Spread Signal Generation ---")
    strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)

    spread_signals = strategy.generate_spread_signals(available_data, option_chain, current_date)

    print(f"Spread signals generated: {len(spread_signals)}")

    if len(spread_signals) > 0:
        print(f"SUCCESS: Fix is working! Generated {len(spread_signals)} spread signals")
        for i, signal in enumerate(spread_signals[:3]):  # Show first 3
            print(f"  Signal {i+1}: {signal.signal_type} {getattr(signal, 'signal_strength', 0.0):.3f} "
                  f"({getattr(signal, 'long_strike', 0.0)}/{getattr(signal, 'short_strike', 0.0)}) "
                  f"option_type: {getattr(signal, 'option_type', 'unknown')}")
            if hasattr(signal, 'net_debit'):
                print(f"    Net debit: ${signal.net_debit:.2f}")
        return True
    else:
        print("FAIL: Still no spread signals generated")
        return False

def test_both_signal_types():
    """Test that both bullish and bearish signals can generate spreads."""
    print("\n" + "=" * 55)
    print("TESTING BOTH SIGNAL TYPES")
    print("=" * 55)

    pipeline = OptionsDataPipeline(symbol="AAPL")
    strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)
    signal_generator = SignalGenerator()

    # Create trending data that should give clear signals
    print("Creating strongly trending test data...")

    # Create data with strong upward trend for bullish signal
    dates = [datetime.now() - timedelta(days=i) for i in range(30, 0, -1)]
    base_price = 100.0
    prices = []

    # Strong upward trend
    for i in range(30):
        price = base_price * (1 + 0.015) ** i * (1 + np.random.normal(0, 0.005))
        prices.append(price)

    bullish_data = pd.DataFrame({
        'date': dates,
        'open': [p * 0.995 for p in prices],
        'high': [p * 1.01 for p in prices],
        'low': [p * 0.99 for p in prices],
        'close': prices,
        'adjusted_close': prices,
        'volume': [np.random.randint(1000000, 5000000) for _ in range(30)],
        'symbol': 'AAPL'
    })

    # Create data with strong downward trend for bearish signal
    prices = []
    for i in range(30):
        price = base_price * (1 - 0.015) ** i * (1 + np.random.normal(0, 0.005))
        prices.append(price)

    bearish_data = pd.DataFrame({
        'date': dates,
        'open': [p * 1.005 for p in prices],
        'high': [p * 1.01 for p in prices],
        'low': [p * 0.99 for p in prices],
        'close': prices,
        'adjusted_close': prices,
        'volume': [np.random.randint(1000000, 5000000) for _ in range(30)],
        'symbol': 'AAPL'
    })

    # Test bullish signal
    print("\nTesting BULLISH signal...")
    current_date = bullish_data['date'].iloc[-1]
    available_bullish = bullish_data[bullish_data['date'] <= current_date].copy()
    option_chain = pipeline.get_option_chain_data(current_date.strftime('%Y-%m-%d'))

    bullish_signal = signal_generator.get_signal(available_bullish, current_date)
    if bullish_signal:
        print(f"  Raw signal: {bullish_signal.signal_type} (strength: {bullish_signal.signal_strength:.3f})")
        bullish_spreads = strategy.generate_spread_signals(available_bullish, option_chain, current_date)
        print(f"  Bullish spread signals: {len(bullish_spreads)}")
    else:
        print("  No bullish signal generated")

    # Test bearish signal
    print("\nTesting BEARISH signal...")
    current_date = bearish_data['date'].iloc[-1]
    available_bearish = bearish_data[bearish_data['date'] <= current_date].copy()
    option_chain = pipeline.get_option_chain_data(current_date.strftime('%Y-%m-%d'))

    bearish_signal = signal_generator.get_signal(available_bearish, current_date)
    if bearish_signal:
        print(f"  Raw signal: {bearish_signal.signal_type} (strength: {bearish_signal.signal_strength:.3f})")
        bearish_spreads = strategy.generate_spread_signals(available_bearish, option_chain, current_date)
        print(f"  Bearish spread signals: {len(bearish_spreads)}")
    else:
        print("  No bearish signal generated")

def main():
    """Main test function."""
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    success = test_fix()
    test_both_signal_types()

    print("\n" + "=" * 55)
    if success:
        print("FIX VERIFICATION: SUCCESS")
        print("The vertical spread strategy can now generate spread signals!")
    else:
        print("FIX VERIFICATION: FAILED")
        print("The vertical spread strategy still cannot generate spread signals.")

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
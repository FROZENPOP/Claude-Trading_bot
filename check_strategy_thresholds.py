#!/usr/bin/env python3
"""Check what thresholds the VerticalSpreadStrategy uses."""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

# Add project to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy

def check_strategy_attributes():
    """Check the strategy's attributes and methods."""
    print("CHECKING VERTICAL SPREAD STRATEGY ATTRIBUTES")
    print("=" * 50)

    strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)

    print("Strategy attributes:")
    for attr in dir(strategy):
        if not attr.startswith('_'):
            try:
                value = getattr(strategy, attr)
                if not callable(value):
                    print(f"  {attr}: {value}")
            except:
                pass  # Some attributes might raise exceptions when accessed

    print("\nChecking for signal-related attributes:")
    signal_attrs = ['min_signal_strength', 'signal_threshold', 'min_strength',
                   'threshold', 'bullish_threshold', 'bearish_threshold']

    for attr in signal_attrs:
        if hasattr(strategy, attr):
            value = getattr(strategy, attr)
            print(f"  {attr}: {value}")
        else:
            print(f"  {attr}: NOT FOUND")

    # Let's look at the generate_spread_signals method source
    print("\nExamining generate_spread_signals logic...")
    import inspect
    try:
        source = inspect.getsource(strategy.generate_spread_signals)
        print(source[:1000])  # First 1000 chars
        if len(source) > 1000:
            print("... (truncated)")
    except Exception as e:
        print(f"Could not get source: {e}")

def test_bearish_signal_handling():
    """Test specifically how the strategy handles bearish signals."""
    print("\n" + "=" * 50)
    print("TESTING BEARISH SIGNAL HANDLING")
    print("=" * 50)

    # Create a mock signal that mimics what we saw
    from trading_bot.strategies.signals import Signal

    # Test bearish signal like we saw: strength 0.810
    bearish_signal = Signal(
        signal_type='bearish',
        signal_strength=0.810,
        metadata={
            'details': 'Momentum: 1D: -0.06%, 5D: -5.21%, 20D: 4.55%',
            'bearish_score': 0.810,
            'bullish_score': 0.100,
            'neutral_score': 0.090
        }
    )

    print(f"Testing bearish signal: {bearish_signal.signal_type} (strength: {bearish_signal.signal_strength})")

    # Check what the strategy considers valid for spread generation
    strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)

    # Let's see if we can find where the strategy filters signals
    # Look at the _generate_bear_put_signals or _generate_bull_call_signals methods

    print("\nChecking if strategy has methods for bearish spreads:")
    if hasattr(strategy, '_generate_bear_put_signals'):
        print("  Has _generate_bear_put_signals method")
        try:
            import inspect
            source = inspect.getsource(strategy._generate_bear_put_signals)
            print("  Source (first 500 chars):")
            print(source[:500])
        except Exception as e:
            print(f"  Could not get source: {e}")
    else:
        print("  Does NOT have _generate_bear_put_signals method")

    if hasattr(strategy, '_generate_bull_call_signals'):
        print("  Has _generate_bull_call_signals method")
    else:
        print("  Does NOT have _generate_bull_call_signals method")

def main():
    """Main function."""
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    check_strategy_attributes()
    test_bearish_signal_handling()

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
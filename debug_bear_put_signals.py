#!/usr/bin/env python3
"""Debug the _generate_bear_put_signals method."""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
import inspect

# Add project to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy

def get_bear_put_source():
    """Get the source of _generate_bear_put_signals."""
    print("SOURCE OF _generate_bear_put_signals METHOD")
    print("=" * 50)

    strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)

    try:
        source = inspect.getsource(strategy._generate_bear_put_signals)
        print(source)
    except Exception as e:
        print(f"Could not get source: {e}")

def debug_bear_put_signals():
    """Debug what's happening in _generate_bear_put_signals."""
    print("\n" + "=" * 50)
    print("DEBUGGING _generate_bear_put_signals EXECUTION")
    print("=" * 50)

    # Monkey patch to add debug prints
    from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy
    original_method = VerticalSpreadStrategy._generate_bear_put_signals

    def debug_generate_bear_put(self, underlying_signal, option_chain, current_date):
        print(f"\n[_generate_bear_put_signals] START")
        print(f"  underlying_signal: {underlying_signal}")
        print(f"  option_chain shape: {option_chain.shape}")
        print(f"  current_date: {current_date}")

        # Call the original method but wrap it in debug
        try:
            result = original_method(self, underlying_signal, option_chain, current_date)
            print(f"[_generate_bear_put_signals] END - returning {len(result)} signals")
            return result
        except Exception as e:
            print(f"[_generate_bear_put_signals] ERROR: {e}")
            raise

    VerticalSpreadStrategy._generate_bear_put_signals = debug_generate_bear_put

    # Also debug the internal steps if possible
    try:
        # Let's also look at what the method does internally by checking its source
        # and potentially breaking it down

        strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)

        # Create test data like we had before
        from research_options_strategies import OptionsDataPipeline
        pipeline = OptionsDataPipeline(symbol="AAPL")

        lookback_start = "2026-07-19"
        end_date = "2026-09-07"

        stock_data = pipeline.get_stock_data(lookback_start, end_date)
        current_date = stock_data['date'].iloc[-1]
        available_data = stock_data[stock_data['date'] <= current_date].copy()
        option_chain = pipeline.get_option_chain_data(end_date)

        # Get the signal
        from trading_bot.strategies.signals import SignalGenerator
        signal_generator = SignalGenerator()
        underlying_signal = signal_generator.get_signal(available_data, current_date)

        print(f"Testing with:")
        print(f"  underlying_signal: {underlying_signal}")
        print(f"  option_chain size: {len(option_chain)}")

        # Now call our debugged method
        signals = strategy._generate_bear_put_signals(underlying_signal, option_chain, current_date)
        print(f"\nResult: {len(signals)} bear put signals")

        if len(signals) > 0:
            for i, signal in enumerate(signals[:3]):
                print(f"  Signal {i+1}: {signal.long_strike}/{signal.short_strike} put, "
                      f"debit: ${signal.net_debit:.2f}")

    except Exception as e:
        print(f"Error during debug: {e}")
        import traceback
        traceback.print_exc()

    # Restore original method
    VerticalSpreadStrategy._generate_bear_put_signals = original_method

def get_full_bear_put_source():
    """Try to get the full source with line numbers."""
    print("\n" + "=" * 50)
    print("FULL SOURCE WITH LINE NUMBERS")
    print("=" * 50)

    try:
        strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)
        lines, start_line = inspect.getsourcelines(strategy._generate_bear_put_signals)

        for i, line in enumerate(lines):
            line_num = start_line + i
            print(f"{line_num:3}: {line.rstrip()}")
    except Exception as e:
        print(f"Could not get sourced lines: {e}")

def main():
    """Main function."""
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    get_bear_put_source()
    get_full_bear_put_source()
    debug_bear_put_signals()

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
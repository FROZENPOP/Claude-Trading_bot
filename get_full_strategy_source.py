#!/usr/bin/env python3
"""Get the full source of the generate_spread_signals method."""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
import inspect

# Add project to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy

def get_full_source():
    """Get and display the full source of generate_spread_signals."""
    print("FULL SOURCE OF generate_spread_signals METHOD")
    print("=" * 60)

    strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)

    try:
        source = inspect.getsource(strategy.generate_spread_signals)
        print(source)
    except Exception as e:
        print(f"Could not get source: {e}")

        # Let's try to get it line by line
        try:
            print("\nTrying to get source lines:")
            lines = inspect.getsourcelines(strategy.generate_spread_signals)[0]
            for i, line in enumerate(lines):
                print(f"{i+1:2}: {line.rstrip()}")
        except Exception as e2:
            print(f"Also failed: {e2}")

def test_with_actual_debug():
    """Test with actual debugging to see what's happening."""
    print("\n" + "=" * 60)
    print("TESTING WITH ACTUAL DEBUG OUTPUT")
    print("=" * 60)

    # Let's monkey patch the method to add debug prints
    from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy
    original_method = VerticalSpreadStrategy.generate_spread_signals

    def debug_generate_spread_signals(self, market_data, option_chain, current_date=None):
        print(f"\n[DEBUG] generate_spread_signals called")
        print(f"  market_data shape: {market_data.shape}")
        print(f"  option_chain shape: {option_chain.shape}")
        print(f"  current_date: {current_date}")

        if current_date is None:
            current_date = datetime.now()

        signals = []

        # Get underlying signal
        underlying_signal = self.signal_generator.get_signal(market_data, current_date)
        print(f"  underlying_signal: {underlying_signal}")

        if underlying_signal is None:
            print("  [DEBUG] underlying_signal is None")
            return signals

        print(f"  underlying_signal.signal_type: {underlying_signal.signal_type}")
        print(f"  underlying_signal.signal_strength: {underlying_signal.signal_strength}")

        if underlying_signal.signal_strength < 0.3:
            print(f"  [DEBUG] signal strength {underlying_signal.signal_strength} < 0.3")
            return signals

        print(f"  [DEBUG] signal strength sufficient, proceeding...")

        # Determine spread type based on signal
        if underlying_signal.signal_type == 'bullish':
            print(f"  [DEBUG] Processing bullish signal")
            # Generate bull call spreads
            bull_signals = self._generate_bull_call_signals(market_data, option_chain, current_date)
            print(f"  [DEBUG] _generate_bull_call_signals returned {len(bull_signals)} signals")
            signals.extend(bull_signals)
        elif underlying_signal.signal_type == 'bearish':
            print(f"  [DEBUG] Processing bearish signal")
            # Generate bear put spreads
            bear_signals = self._generate_bear_put_signals(market_data, option_chain, current_date)
            print(f"  [DEBUG] _generate_bear_put_signals returned {len(bear_signals)} signals")
            signals.extend(bear_signals)
        else:
            print(f"  [DEBUG] Signal type '{underlying_signal.signal_type}' not bullish or bearish, skipping")

        print(f"  [DEBUG] Returning {len(signals)} total signals")
        return signals

    # Replace the method
    VerticalSpreadStrategy.generate_spread_signals = debug_generate_spread_signals

    # Also debug the spread generation methods
    original_bull = VerticalSpreadStrategy._generate_bull_call_signals
    original_bear = VerticalSpreadStrategy._generate_bear_put_signals

    def debug_bull_call(self, market_data, option_chain, current_date):
        print(f"    [_generate_bull_call_signals] Called")
        result = original_bull(self, market_data, option_chain, current_date)
        print(f"    [_generate_bull_call_signals] Returning {len(result)} signals")
        return result

    def debug_bear_put(self, market_data, option_chain, current_date):
        print(f"    [_generate_bear_put_signals] Called")
        result = original_bear(self, market_data, option_chain, current_date)
        print(f"    [_generate_bear_put_signals] Returning {len(result)} signals")
        return result

    VerticalSpreadStrategy._generate_bull_call_signals = debug_bull_call
    VerticalSpreadStrategy._generate_bear_put_signals = debug_bear_put

    # Now run our test
    from research_options_strategies import OptionsDataPipeline

    pipeline = OptionsDataPipeline(symbol="AAPL")

    # Test the bearish signal case we saw
    lookback_start = "2026-07-19"
    end_date = "2026-09-07"

    print(f"\nTesting {lookback_start} to {end_date}")

    stock_data = pipeline.get_stock_data(lookback_start, end_date)

    if not stock_data.empty:
        current_date = stock_data['date'].iloc[-1]
        available_data = stock_data[stock_data['date'] <= current_date].copy()
        option_chain = pipeline.get_option_chain_data(end_date)

        print(f"Stock data: {len(available_data)} rows")
        print(f"Option chain: {len(option_chain)} contracts")

        strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)
        signals = strategy.generate_spread_signals(available_data, option_chain, current_date)

        print(f"\nFINAL RESULT: {len(signals)} spread signals")

    # Restore original methods
    VerticalSpreadStrategy.generate_spread_signals = original_method
    VerticalSpreadStrategy._generate_bull_call_signals = original_bull
    VerticalSpreadStrategy._generate_bear_put_signals = original_bear

if __name__ == "__main__":
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    get_full_source()
    test_with_actual_debug()
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
#!/usr/bin/env python3
"""Detailed debug of the fixed strategy."""

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

def debug_detailed():
    """Debug with detailed output."""
    print("DETAILED DEBUG OF FIXED STRATEGY")
    print("=" * 40)

    # Monkey patch the methods to add debug prints
    from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy

    # Save original methods
    original_bull = VerticalSpreadStrategy._generate_bull_call_signals
    original_bear = VerticalSpreadStrategy._generate_bear_put_signals
    original_get_underlying = VerticalSpreadStrategy._get_underlying_price

    def debug_bull_call(self, signal, option_chain, market_data, current_date):
        print(f"\n[_generate_bull_call_signals] DEBUG:")
        print(f"  signal: {signal}")
        print(f"  option_chain shape: {option_chain.shape}")
        print(f"  market_data shape: {market_data.shape}")
        print(f"  current_date: {current_date}")

        result = original_bull(self, signal, option_chain, market_data, current_date)
        print(f"[_generate_bull_call_signals] RESULT: {len(result)} signals")
        return result

    def debug_bear_put(self, signal, option_chain, market_data, current_date):
        print(f"\n[_generate_bear_put_signals] DEBUG:")
        print(f"  signal: {signal}")
        print(f"  option_chain shape: {option_chain.shape}")
        print(f"  market_data shape: {market_data.shape}")
        print(f"  current_date: {current_date}")

        result = original_bear(self, signal, option_chain, market_data, current_date)
        print(f"[_generate_bear_put_signals] RESULT: {len(result)} signals")
        return result

    def debug_get_underlying(self, market_data, current_date):
        print(f"[_get_underlying_price] DEBUG:")
        print(f"  market_data is None: {market_data is None}")
        if market_data is not None:
            print(f"  market_data shape: {market_data.shape}")
            if not market_data.empty:
                print(f"  market_data columns: {list(market_data.columns)}")
                if 'adjusted_close' in market_data.columns:
                    adj_close = market_data['adjusted_close'].iloc[-1]
                    print(f"  adjusted_close[-1]: {adj_close}")
                if 'close' in market_data.columns:
                    close_price = market_data['close'].iloc[-1]
                    print(f"  close[-1]: {close_price}")

        result = original_get_underlying(self, market_data, current_date)
        print(f"[_get_underlying_price] RESULT: {result}")
        return result

    # Apply patches
    VerticalSpreadStrategy._generate_bull_call_signals = debug_bull_call
    VerticalSpreadStrategy._generate_bear_put_signals = debug_bear_put
    VerticalSpreadStrategy._get_underlying_price = debug_get_underlying

    # Now run the test
    pipeline = OptionsDataPipeline(symbol="AAPL")
    signal_generator = SignalGenerator()

    # Use the same test case
    lookback_start = "2026-07-19"
    end_date = "2026-09-07"

    print(f"Loading data from {lookback_start} to {end_date}")

    stock_data = pipeline.get_stock_data(lookback_start, end_date)

    if not stock_data.empty:
        current_date = stock_data['date'].iloc[-1]
        available_data = stock_data[stock_data['date'] <= current_date].copy()
        option_chain = pipeline.get_option_chain_data(end_date)

        print(f"Stock data: {len(available_data)} rows")
        print(f"Option chain: {len(option_chain)} contracts")
        print(f"Current date: {current_date}")

        # Test signal generation
        raw_signal = signal_generator.get_signal(available_data, current_date)
        print(f"\nRaw signal: {raw_signal}")

        if raw_signal is not None and raw_signal.signal_strength >= 0.3:
            # Test strategy
            strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)
            spread_signals = strategy.generate_spread_signals(available_data, option_chain, current_date)
            print(f"\nFINAL RESULT: {len(spread_signals)} spread signals")
        else:
            print("Signal too weak or None")

    # Restore original methods
    VerticalSpreadStrategy._generate_bull_call_signals = original_bull
    VerticalSpreadStrategy._generate_bear_put_signals = original_bear
    VerticalSpreadStrategy._get_underlying_price = original_get_underlying

if __name__ == "__main__":
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    debug_detailed()
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
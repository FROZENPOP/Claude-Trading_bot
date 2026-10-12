#!/usr/bin/env python3
"""Debug the internal logic of _generate_bear_put_signals."""

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

def debug_bear_put_internal():
    """Debug the internal logic of bear put signal generation."""
    print("INTERNAL DEBUG OF _generate_bear_put_signals")
    print("=" * 50)

    # Monkey patch to add detailed debug inside the method
    from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy
    original_method = VerticalSpreadStrategy._generate_bear_put_signals

    def debug_method(self, signal, option_chain, market_data, current_date):
        print(f"\n[_generate_bear_put_signals] ENTERED:")
        print(f"  signal strength: {signal.signal_strength}")
        print(f"  signal type: {signal.signal_type}")
        print(f"  option_chain rows: {len(option_chain)}")
        print(f"  market_data rows: {len(market_data)}")
        print(f"  current_date: {current_date}")

        # Get underlying price (we know this works now)
        underlying_price = self._get_underlying_price(market_data, current_date)
        print(f"  underlying_price: {underlying_price}")

        if underlying_price is None:
            print("  ERROR: underlying_price is None!")
            return []

        # Check what strikes we're looking for
        target_put_strike = underlying_price * (1 - self.put_otm_percentage)
        target_call_strike = underlying_price * (1 + self.call_otm_percentage)

        print(f"  put_otm_percentage: {self.put_otm_percentage}")
        print(f"  call_otm_percentage: {self.call_otm_percentage}")
        print(f"  target_put_strike: {target_put_strike}")
        print(f"  target_call_strike: {target_call_strike}")

        # Filter option chain for puts and calls near current date
        puts = option_chain[
            (option_chain['option_type'] == 'put') &
            (option_chain['expiration_date'] >= current_date)
        ].copy()

        calls = option_chain[
            (option_chain['option_type'] == 'call') &
            (option_chain['expiration_date'] >= current_date)
        ].copy()

        print(f"  filtered puts: {len(puts)}")
        print(f"  filtered calls: {len(calls)}")

        if len(puts) == 0 or len(calls) == 0:
            print("  ERROR: No puts or calls after filtering!")
            return []

        # Find closest strikes
        puts['strike_diff'] = abs(puts['strike'] - target_put_strike)
        calls['strike_diff'] = abs(calls['strike'] - target_call_strike)

        closest_put = puts.loc[puts['strike_diff'].idxmin()]
        closest_call = calls.loc[calls['strike_diff'].idxmin()]

        print(f"  closest_put: strike={closest_put['strike']}, diff={closest_put['strike_diff']:.2f}")
        print(f"  closest_call: strike={closest_call['strike']}, diff={closest_call['strike_diff']:.2f}")

        # Check if we have bid/ask data
        print(f"  closest_put bid: {closest_put.get('bid', 'N/A')}, ask: {closest_put.get('ask', 'N/A')}")
        print(f"  closest_call bid: {closest_call.get('bid', 'N/A')}, ask: {closest_call.get('ask', 'N/A')}")

        # Calculate mid prices
        if pd.notna(closest_put['bid']) and pd.notna(closest_put['ask']):
            put_mid = (closest_put['bid'] + closest_put['ask']) / 2
            print(f"  put_mid: {put_mid}")
        else:
            print("  WARNING: Put missing bid/ask data")
            put_mid = None

        if pd.notna(closest_call['bid']) and pd.notna(closest_call['ask']):
            call_mid = (closest_call['bid'] + closest_call['ask']) / 2
            print(f"  call_mid: {call_mid}")
        else:
            print("  WARNING: Call missing bid/ask data")
            call_mid = None

        # Only proceed if we have both mids
        if put_mid is not None and call_mid is not None:
            # For bear put spread: we BUY the put and SELL the call
            net_debit = put_mid - call_mid
            print(f"  bear put spread net_debit: {net_debit} (put_mid: {put_mid} - call_mid: {call_mid})")

            max_profit = closest_put['strike'] - closest_call['strike'] - net_debit
            print(f"  max_profit: {max_profit} (put_strike: {closest_put['strike']} - call_strike: {closest_call['strike']} - net_debit: {net_debit})")

            if max_profit > 0:
                print(f"  SUCCESS: Would create signal with max_profit={max_profit}")
                # Normally would return a signal here
                return [{"test": "signal"}]
            else:
                print(f"  REJECTED: max_profit <= 0 ({max_profit})")
        else:
            print("  ERROR: Missing mid prices for calculation")

        print("  RETURNING: [] (no signals)")
        return []

    # Apply patch
    VerticalSpreadStrategy._generate_bear_put_signals = debug_method

    # Run test
    pipeline = OptionsDataPipeline(symbol="AAPL")
    signal_generator = SignalGenerator()

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

    # Restore original method
    VerticalSpreadStrategy._generate_bear_put_signals = original_method

if __name__ == "__main__":
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    debug_bear_put_internal()
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
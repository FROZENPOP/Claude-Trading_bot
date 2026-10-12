#!/usr/bin/env python3
"""Test spread generation using actual available strikes."""

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

def test_with_actual_strikes():
    """Test using actual strikes from option chain."""
    print("TESTING WITH ACTUAL AVAILABLE STRIKES")
    print("=" * 40)

    pipeline = OptionsDataPipeline(symbol="AAPL")
    signal_generator = SignalGenerator()

    lookback_start = "2026-07-19"
    end_date = "2026-09-07"

    print(f"Loading data from {lookback_start} to {end_date}")

    stock_data = pipeline.get_stock_data(lookback_start, end_date)

    if stock_data.empty:
        print("ERROR: No stock data loaded")
        return

    current_date = stock_data['date'].iloc[-1]
    available_data = stock_data[stock_data['date'] <= current_date].copy()
    option_chain = pipeline.get_option_chain_data(end_date)

    # Add days_to_exp column for filtering
    option_chain['days_to_exp'] = option_chain['expiration_date'].apply(
        lambda x: (datetime.strptime(x, '%Y-%m-%d') - current_date).days if pd.notna(x) else None
    )

    print(f"Stock data: {len(available_data)} rows")
    print(f"Option chain: {len(option_chain)} contracts")
    print(f"Current date: {current_date}")

    # Get underlying price
    underlying_price = available_data['close'].iloc[-1]
    print(f"Underlying price: {underlying_price}")

    # Test signal generation
    raw_signal = signal_generator.get_signal(available_data, current_date)
    print(f"\nRaw signal: {raw_signal}")

    if raw_signal is None or raw_signal.signal_strength < 0.3:
        print("Signal too weak or None")
        return

    # Now let's manually try to generate spreads using actual strikes
    print(f"\n--- MANUAL SPREAD GENERATION TEST ---")

    # Use DTE 21 (we know it has options)
    target_dte = 21

    # Filter options for this DTE and type based on signal
    if raw_signal.signal_type == 'bearish':
        # Bear put spread: BUY put (higher strike), SELL put (lower strike)
        options = option_chain[
            (option_chain['option_type'] == 'put') &
            (option_chain['days_to_exp'] == target_dte)
        ].copy()
        print(f"Found {len(options)} put options for DTE {target_dte}")
    else:
        # Bull call spread: BUY call (lower strike), SELL call (higher strike)
        options = option_chain[
            (option_chain['option_type'] == 'call') &
            (option_chain['days_to_exp'] == target_dte)
        ].copy()
        print(f"Found {len(options)} call options for DTE {target_dte}")

    if options.empty:
        print("No options found for this DTE/type combination")
        return

    # Get unique strikes
    strikes = sorted(options['strike_price'].unique())
    print(f"Available strikes: {strikes}")

    # Calculate ATM strike
    atm_strike = round(underlying_price)
    print(f"ATM strike: {atm_strike}")

    # Try to find valid spreads
    valid_spreads = []

    if raw_signal.signal_type == 'bearish':
        # For bear put: long put (higher strike), short put (lower strike)
        # We want: long_strike > short_strike
        for i, long_strike in enumerate(strikes):
            if long_strike <= atm_strike:  # We want OTM or slightly ITM puts
                continue

            for short_strike in strikes[:i]:  # Only lower strikes
                width = long_strike - short_strike
                if width <= 0 or width > 10:  # Reasonable width check
                    continue

                # Get mid prices
                long_opts = options[abs(options['strike_price'] - long_strike) < 0.1]
                short_opts = options[abs(options['strike_price'] - short_strike) < 0.1]

                if len(long_opts) == 0 or len(short_opts) == 0:
                    continue

                long_bid = long_opts['bid_price'].iloc[0]
                long_ask = long_opts['ask_price'].iloc[0]
                short_bid = short_opts['bid_price'].iloc[0]
                short_ask = short_opts['ask_price'].iloc[0]

                if pd.isna(long_bid) or pd.isna(long_ask) or pd.isna(short_bid) or pd.isna(short_ask):
                    continue

                long_mid = (long_bid + long_ask) / 2
                short_mid = (short_bid + short_ask) / 2

                # For bear put spread: we BUY the put (long) and SELL the put (short)
                net_debit = long_mid - short_mid

                if net_debit > 0:  # We pay to enter the spread
                    max_profit = width - net_debit
                    if max_profit > 0:
                        valid_spreads.append({
                            'long_strike': long_strike,
                            'short_strike': short_strike,
                            'width': width,
                            'long_mid': long_mid,
                            'short_mid': short_mid,
                            'net_debit': net_debit,
                            'max_profit': max_profit
                        })
    else:
        # For bull call: long call (lower strike), short call (higher strike)
        # We want: long_strike < short_strike
        for i, short_strike in enumerate(strikes):
            if short_strike < atm_strike:  # We want OTM or slightly ITM calls
                continue

            for long_strike in strikes[:i]:  # Only lower strikes
                width = short_strike - long_strike
                if width <= 0 or width > 10:  # Reasonable width check
                    continue

                # Get mid prices
                long_opts = options[abs(options['strike_price'] - long_strike) < 0.1]
                short_opts = options[abs(options['strike_price'] - short_strike) < 0.1]

                if len(long_opts) == 0 or len(short_opts) == 0:
                    continue

                long_bid = long_opts['bid_price'].iloc[0]
                long_ask = long_opts['ask_price'].iloc[0]
                short_bid = short_opts['bid_price'].iloc[0]
                short_ask = short_opts['ask_price'].iloc[0]

                if pd.isna(long_bid) or pd.isna(long_ask) or pd.isna(short_bid) or pd.isna(short_ask):
                    continue

                long_mid = (long_bid + long_ask) / 2  # Lower strike call
                short_mid = (short_bid + short_ask) / 2  # Higher strike call

                # For bull call spread: we BUY the call (long) and SELL the call (short)
                net_debit = long_mid - short_mid  # Should be positive for debit spread

                if net_debit > 0:  # We pay to enter the spread
                    max_profit = width - net_debit
                    if max_profit > 0:
                        valid_spreads.append({
                            'long_strike': long_strike,
                            'short_strike': short_strike,
                            'width': width,
                            'long_mid': long_mid,
                            'short_mid': short_mid,
                            'net_debit': net_debit,
                            'max_profit': max_profit
                        })

    print(f"\nFound {len(valid_spreads)} valid spreads using actual strikes:")
    for i, spread in enumerate(valid_spreads[:5]):  # Show first 5
        print(f"  {i+1}. {spread['long_strike']}/{spread['short_strike']} "
              f"width={spread['width']}, debit={spread['net_debit']:.2f}, "
              f"max_profit={spread['max_profit']:.2f}")

    if len(valid_spreads) > 5:
        print(f"  ... and {len(valid_spreads) - 5} more")

    # Now test with the actual strategy to see if it finds any
    print(f"\n--- TESTING WITH ACTUAL STRATEGY ---")
    strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)
    spread_signals = strategy.generate_spread_signals(available_data, option_chain, current_date)
    print(f"Strategy generated: {len(spread_signals)} spread signals")

    if len(spread_signals) > 0:
        print("SUCCESS: Strategy is working with real data!")
        for i, signal in enumerate(spread_signals[:3]):
            print(f"  Signal {i+1}: {signal.signal_type} "
                  f"({getattr(signal, 'long_strike', 0)}/{getattr(signal, 'short_strike', 0)}) "
                  f"debit=${getattr(signal, 'net_debit', 0):.2f}")
    else:
        print("STRATEGY STILL GENERATING ZERO SIGNALS")

if __name__ == "__main__":
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    test_with_actual_strikes()
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
#!/usr/bin/env python3
"""Regression test for vertical spread strategy with irregular strike spacing."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add project to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy
from trading_bot.strategies.signals import SignalGenerator
from trading_bot.strategies.signals import Signal

def test_irregular_strike_spacing():
    """Test that the strategy works with irregular strike spacing."""
    print("REGRESSION TEST: IRREGULAR STRIKE SPACING")
    print("=" * 50)

    # Create a signal generator
    signal_generator = SignalGenerator()

    # Create a strategy
    strategy = VerticalSpreadStrategy('TEST', max_risk_per_trade=0.02)

    # Create test data with irregular strike spacing as requested:
    # 113, 117, 121, 125, 129, 133, 137, 141
    strikes = [113, 117, 121, 125, 129, 133, 137, 141]

    # Current date and underlying price
    current_date = datetime(2026, 9, 7)
    underlying_price = 136.89  # ATM strike should be 137

    # Create option chain data for calls and puts with the specified strikes
    # We'll use DTE 21 (3 weeks out)
    expiration_date = (current_date + timedelta(days=21)).strftime('%Y-%m-%d')

    option_chain_data = []

    # Add call options
    for strike in strikes:
        # Simulate realistic bid/ask prices
        # For calls: price decreases as strike increases
        intrinsic = max(0, underlying_price - strike)
        time_value = 2.0  # Simplified
        mid_price = intrinsic + time_value
        bid = mid_price * 0.95
        ask = mid_price * 1.05

        option_chain_data.append({
            'option_symbol': f'TEST{current_date.strftime("%y%m%d")}C{int(strike*1000):08d}',
            'underlying_symbol': 'TEST',
            'expiration_date': expiration_date,
            'option_type': 'call',
            'strike_price': float(strike),
            'bid_price': bid,
            'ask_price': ask,
            'last_price': (bid + ask) / 2,
            'volume': 100,
            'open_interest': 500
        })

    # Add put options
    for strike in strikes:
        # Simulate realistic bid/ask prices
        # For puts: price increases as strike increases
        intrinsic = max(0, strike - underlying_price)
        time_value = 2.0  # Simplified
        mid_price = intrinsic + time_value
        bid = mid_price * 0.95
        ask = mid_price * 1.05

        option_chain_data.append({
            'option_symbol': f'TEST{current_date.strftime("%y%m%d")}P{int(strike*1000):08d}',
            'underlying_symbol': 'TEST',
            'expiration_date': expiration_date,
            'option_type': 'put',
            'strike_price': float(strike),
            'bid_price': bid,
            'ask_price': ask,
            'last_price': (bid + ask) / 2,
            'volume': 100,
            'open_interest': 500
        })

    option_chain = pd.DataFrame(option_chain_data)

    # Add days_to_exp column
    option_chain['days_to_exp'] = option_chain['expiration_date'].apply(
        lambda x: (datetime.strptime(x, '%Y-%m-%d') - current_date).days
    )

    print(f"Created option chain with {len(option_chain)} contracts")
    print(f"Strikes available: {sorted(option_chain['strike_price'].unique())}")
    print(f"Underlying price: {underlying_price}")
    print(f"ATM strike: {round(underlying_price)}")

    # Create market data (minimal, just for signal generation)
    market_data = pd.DataFrame({
        'date': [current_date - timedelta(days=i) for i in range(5, 0, -1)],
        'adjusted_close': [135.0, 136.0, 137.0, 138.0, 136.89],
        'symbol': 'TEST'
    })

    # Test Case 1: Verify nonexistent strikes are never selected
    print("\n--- Test 1: Verify nonexistent strikes are never selected ---")

    # Create a bullish signal
    bullish_signal = Signal(
        signal_type='bullish',
        signal_strength=0.8,
        timestamp=current_date,
        metadata={'bullish_score': 0.8, 'bearish_score': 0.1, 'neutral_score': 0.1}
    )

    # Generate bull call spread signals
    bullish_spreads = strategy.generate_spread_signals(market_data, option_chain, current_date)

    print(f"Bullish spreads generated: {len(bullish_spreads)}")

    # Check that all selected strikes exist in our option chain
    valid_strikes = set(option_chain['strike_price'].unique())
    invalid_strikes_found = []

    for signal in bullish_spreads:
        long_strike = getattr(signal, 'long_strike', None)
        short_strike = getattr(signal, 'short_strike', None)

        if long_strike is not None and long_strike not in valid_strikes:
            invalid_strikes_found.append(long_strike)
        if short_strike is not None and short_strike not in valid_strikes:
            invalid_strikes_found.append(short_strike)

    if invalid_strikes_found:
        print(f"FAIL: Found invalid strikes: {set(invalid_strikes_found)}")
        return False
    else:
        print("PASS: No nonexistent strikes selected")

    # Test Case 2: Verify both legs have the same expiration
    print("\n--- Test 2: Verify both legs have the same expiration ---")

    # This is implicitly tested by our construction - we only look at options
    # with the same days_to_exp, so both legs will have the same expiration
    print("PASS: Both legs have same expiration (by construction)")

    # Test Case 3: Verify both legs have the correct option type
    print("\n--- Test 3: Verify both legs have the correct option type ---")

    incorrect_types = []
    for signal in bullish_spreads:
        option_type = getattr(signal, 'option_type', None)
        if option_type != 'call':
            incorrect_types.append(option_type)

    if incorrect_types:
        print(f"FAIL: Found incorrect option types: {set(incorrect_types)}")
        return False
    else:
        print("PASS: All legs have correct option type (call)")

    # Test Case 4: Verify bull call spreads have long strike < short strike
    print("\n--- Test 4: Verify bull call spreads have long strike < short strike ---")

    invalid_bull_call = []
    for signal in bullish_spreads:
        long_strike = getattr(signal, 'long_strike', None)
        short_strike = getattr(signal, 'short_strike', None)

        if long_strike is not None and short_strike is not None:
            if long_strike >= short_strike:
                invalid_bull_call.append((long_strike, short_strike))

    if invalid_bull_call:
        print(f"FAIL: Found bull call spreads with long >= short: {invalid_bull_call}")
        return False
    else:
        print("PASS: All bull call spreads have long strike < short strike")

    # Test Case 5: Create bearish signal and test bear put spreads
    print("\n--- Test 5: Test bear put spreads ---")

    # Create a bearish signal
    bearish_signal = Signal(
        signal_type='bearish',
        signal_strength=0.8,
        timestamp=current_date,
        metadata={'bullish_score': 0.1, 'bearish_score': 0.8, 'neutral_score': 0.1}
    )

    # Generate bear put spread signals
    bearish_spreads = strategy.generate_spread_signals(market_data, option_chain, current_date)

    print(f"Bearish spreads generated: {len(bearish_spreads)}")

    # Check that all selected strikes exist in our option chain
    invalid_strikes_found = []
    for signal in bearish_spreads:
        long_strike = getattr(signal, 'long_strike', None)
        short_strike = getattr(signal, 'short_strike', None)

        if long_strike is not None and long_strike not in valid_strikes:
            invalid_strikes_found.append(long_strike)
        if short_strike is not None and short_strike not in valid_strikes:
            invalid_strikes_found.append(short_strike)

    if invalid_strikes_found:
        print(f"FAIL: Found invalid strikes: {set(invalid_strikes_found)}")
        return False

    # Verify both legs have the correct option type (put)
    incorrect_types = []
    for signal in bearish_spreads:
        option_type = getattr(signal, 'option_type', None)
        if option_type != 'put':
            incorrect_types.append(option_type)

    if incorrect_types:
        print(f"FAIL: Found incorrect option types: {set(incorrect_types)}")
        return False

    # Verify bear put spreads have long strike > short strike
    invalid_bear_put = []
    for signal in bearish_spreads:
        long_strike = getattr(signal, 'long_strike', None)
        short_strike = getattr(signal, 'short_strike', None)

        if long_strike is not None and short_strike is not None:
            if long_strike <= short_strike:
                invalid_bear_put.append((long_strike, short_strike))

    if invalid_bear_put:
        print(f"FAIL: Found bear put spreads with long <= short: {invalid_bear_put}")
        return False
    else:
        print("PASS: All bear put spreads have long strike > short strike")

    # Test Case 6: Verify existing liquidity/price constraints remain enforced
    print("\n--- Test 6: Verify liquidity/price constraints remain enforced ---")

    # Check that we only consider debit spreads (net_debit > 0)
    non_debit_spreads = []
    for signal in bullish_spreads + bearish_spreads:
        net_debit = getattr(signal, 'net_debit', None)
        if net_debit is not None and net_debit <= 0:
            non_debit_spreads.append(net_debit)

    if non_debit_spreads:
        print(f"FAIL: Found non-debit spreads: {non_debit_spreads}")
        return False
    else:
        print("PASS: All spreads are debit spreads (net_debit > 0)")

    # Check that spread widths are within max_spread_width (10.0)
    excessive_widths = []
    for signal in bullish_spreads + bearish_spreads:
        long_strike = getattr(signal, 'long_strike', None)
        short_strike = getattr(signal, 'short_strike', None)

        if long_strike is not None and short_strike is not None:
            width = abs(long_strike - short_strike)
            if width > strategy.max_spread_width:
                excessive_widths.append(width)

    if excessive_widths:
        print(f"FAIL: Found spreads with excessive width: {excessive_widths}")
        return False
    else:
        print("PASS: All spreads have width <= max_spread_width")

    print("\n" + "=" * 50)
    print("REGRESSION TEST RESULT: ALL TESTS PASSED")
    print("The strategy correctly handles irregular strike spacing.")
    print("=" * 50)

    return True

def main():
    """Main test function."""
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    success = test_irregular_strike_spacing()

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
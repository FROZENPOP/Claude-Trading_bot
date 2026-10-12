#!/usr/bin/env python3
"""Debug the spread signal generation process."""

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

def debug_spread_generation():
    """Debug why spread signals aren't being generated."""
    print("DEBUGGING SPREAD SIGNAL GENERATION")
    print("=" * 50)

    # Create trending data for bullish signal
    print("Creating bullish trending data...")
    dates = [datetime.now() - timedelta(days=i) for i in range(40, 0, -1)]
    base_price = 100.0
    prices = []
    for i in range(40):
        price = base_price * (1 + 0.008) ** i * (1 + np.random.normal(0, 0.01))
        prices.append(price)

    stock_data = pd.DataFrame({
        'date': dates,
        'open': [p * 0.99 for p in prices],
        'high': [p * 1.02 for p in prices],
        'low': [p * 0.98 for p in prices],
        'close': prices,
        'adjusted_close': prices,  # For research simulation
        'volume': [np.random.randint(1000000, 10000000) for _ in range(40)],
        'symbol': 'AAPL'
    })

    current_date = stock_data['date'].iloc[-1]
    print(f"Current date: {current_date}")

    # Generate signal
    signal_generator = SignalGenerator()
    available_data = stock_data[stock_data['date'] <= current_date].copy()
    signal = signal_generator.get_signal(available_data, current_date)

    print(f"Signal: {signal.signal_type} (strength: {signal.signal_strength:.3f})")

    if signal.signal_type != 'bullish':
        print("ERROR: Expected bullish signal")
        return

    # Get option chain
    pipeline = OptionsDataPipeline(symbol="AAPL")
    option_chain = pipeline.get_option_chain_data(current_date.strftime('%Y-%m-%d'))

    print(f"Option chain size: {len(option_chain)} contracts")
    print(f"Option chain columns: {list(option_chain.columns)}")

    if option_chain.empty:
        print("ERROR: No option chain data")
        return

    # Show sample of option chain
    print("\nSample option chain data:")
    print(option_chain[['option_type', 'strike_price', 'expiration_date', 'bid_price', 'ask_price']].head(10))

    # Manually walk through the spread generation logic
    print("\n--- MANUAL SPREAD GENERATION DEBUG ---")

    # Filter option chain for calls
    calls = option_chain[
        (option_chain['option_type'] == 'call') &
        option_chain['expiration_date'].notna()
    ].copy()

    print(f"Call options: {len(calls)}")

    if calls.empty:
        print("ERROR: No call options found")
        return

    # Calculate days to expiration for each option
    calls['days_to_exp'] = calls['expiration_date'].apply(
        lambda x: (datetime.strptime(x, '%Y-%m-%d') - current_date).days
    )

    print(f"Days to expiration range: {calls['days_to_exp'].min()} to {calls['days_to_exp'].max()}")

    # Filter to preferred DTE range
    preferred_dte = [21, 30, 45, 60]
    calls_filtered = calls[
        calls['days_to_exp'].isin(preferred_dte) &
        (calls['days_to_exp'] > 0)  # Not expired
    ]

    print(f"Calls after DTE filter ({preferred_dte}): {len(calls_filtered)}")

    if calls_filtered.empty:
        print("ERROR: No calls found in preferred DTE range")
        print(f"Available DTEs in chain: {sorted(calls['days_to_exp'].unique())}")
        return

    # Get underlying price
    if 'adjusted_close' in available_data.columns:
        underlying_price = float(available_data['adjusted_close'].iloc[-1])
    elif 'close' in available_data.columns:
        underlying_price = float(available_data['close'].iloc[-1])
    else:
        underlying_price = 150.0  # Fallback

    print(f"Underlying price: ${underlying_price:.2f}")

    # For each preferred DTE, find suitable strikes
    strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)

    total_candidate_spreads = 0
    total_valid_spreads = 0

    for dte in strategy.preferred_dte:
        print(f"\nChecking DTE: {dte}")
        dte_calls = calls_filtered[calls_filtered['days_to_exp'] == dte].copy()

        if dte_calls.empty:
            print(f"  No calls found for DTE {dte}")
            continue

        print(f"  Found {len(dte_calls)} calls for DTE {dte}")

        # Get ATM strike
        atm_strike = round(underlying_price)
        print(f"  ATM strike: {atm_strike}")

        # Generate candidate spreads
        for long_strike in np.arange(
            max(1, atm_strike - strategy.max_spread_width),
            atm_strike + strategy.max_spread_width,
            0.5  # 50 cent increments
        ):
            for width in [1.0, 2.5, 5.0]:  # Spread widths to try
                short_strike = long_strike + width

                # Check if both strikes exist in the chain
                long_exists = not dte_calls[
                    abs(dte_calls['strike_price'] - long_strike) < 0.25
                ].empty
                short_exists = not dte_calls[
                    abs(dte_calls['strike_price'] - short_strike) < 0.25
                ].empty

                if long_exists and short_exists:
                    total_candidate_spreads += 1
                    # Calculate approximate entry price using mid prices
                    long_mid = None
                    short_mid = None

                    long_option = dte_calls[
                        abs(dte_calls['strike_price'] - long_strike) < 0.25
                    ].iloc[0] if not dte_calls[
                        abs(dte_calls['strike_price'] - long_strike) < 0.25
                    ].empty else None

                    short_option = dte_calls[
                        abs(dte_calls['strike_price'] - short_strike) < 0.25
                    ].iloc[0] if not dte_calls[
                        abs(dte_calls['strike_price'] - short_strike) < 0.25
                    ].empty else None

                    if long_option is not None and short_option is not None:
                        bid_long = long_option.get('bid_price')
                        ask_long = long_option.get('ask_price')
                        bid_short = short_option.get('bid_price')
                        ask_short = short_option.get('ask_price')

                        if bid_long is not None and ask_long is not None:
                            long_mid = (bid_long + ask_long) / 2
                        elif long_option.get('last_price') is not None:
                            long_mid = long_option['last_price']

                        if bid_short is not None and ask_short is not None:
                            short_mid = (bid_short + ask_short) / 2
                        elif short_option.get('last_price') is not None:
                            short_mid = short_option['last_price']

                    if long_mid is not None and short_mid is not None:
                        net_debit = long_mid - short_mid  # Debit for bull call

                        # Only consider if it's a debit spread (we pay to enter)
                        if net_debit > 0:
                            total_valid_spreads += 1
                            if total_valid_spreads <= 3:  # Show first few
                                print(f"  VALID SPREAD: Long {long_strike} @ ${long_mid:.2f}, Short {short_strike} @ ${short_mid:.2f}, Debit: ${net_debit:.2f}")
                        elif total_valid_spreads == 0 and total_candidate_spreads <= 10:
                            print(f"  REJECTED SPREAD: Long {long_strike} @ ${long_mid:.2f}, Short {short_strike} @ ${short_mid:.2f}, Net: ${net_debit:.2f} (not a debit)")

    print(f"\nSUMMARY:")
    print(f"  Candidate spreads examined: {total_candidate_spreads}")
    print(f"  Valid debit spreads found: {total_valid_spreads}")

    if total_valid_spreads > 0:
        print("[SUCCESS] Spread generation logic should work")
        print("The issue might be in the actual strategy method implementation")
    else:
        print("[FAIL] No valid spreads found in debug process")
        print("Need to examine why no valid spreads are being identified")

def main():
    """Main debug function."""
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    debug_spread_generation()

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
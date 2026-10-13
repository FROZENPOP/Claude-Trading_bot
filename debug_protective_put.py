#!/usr/bin/env python3
"""Debug script for protective put strategy."""

import sys
import os
sys.path.insert(0, '.')

import pandas as pd
from datetime import datetime, timedelta

from trading_bot.strategies.protective_put import ProtectivePutStrategy
from trading_bot.strategies.signals import SignalGenerator

def create_sample_data():
    """Create sample option chain and market data for testing."""
    # Create sample option chain data
    sample_data = []
    base_date = datetime.now() + timedelta(days=46)  # Add extra day to compensate for time portion
    exp_date = base_date.strftime('%Y-%m-%d')
    print(f"Base date: {base_date}")
    print(f"Expiration date string: {exp_date}")
    print(f"Current date: {datetime.now()}")
    print(f"Expected DTE: {(base_date - datetime.now()).days}")

    # Generate sample calls and puts around ATM
    underlying_price = 150.0
    for strike in [140, 145, 150, 155, 160, 165, 170]:
        # Call option
        sample_data.append({
            'option_symbol': f'AAPL{base_date.strftime("%y%m%d")}C{int(strike*1000):08d}',
            'underlying_symbol': 'AAPL',
            'expiration_date': exp_date,
            'option_type': 'call',
            'strike_price': strike,
            'bid_price': max(0, underlying_price - strike + 5.0) * 0.8,
            'ask_price': max(0, underlying_price - strike + 5.0) * 0.9,
            'last_price': max(0, underlying_price - strike + 5.0) * 0.85,
            'volume': 100,
            'open_interest': 500
        })

        # Put option
        sample_data.append({
            'option_symbol': f'AAPL{base_date.strftime("%y%m%d")}P{int(strike*1000):08d}',
            'underlying_symbol': 'AAPL',
            'expiration_date': exp_date,
            'option_type': 'put',
            'strike_price': strike,
            'bid_price': max(0, strike - underlying_price + 5.0) * 0.8,
            'ask_price': max(0, strike - underlying_price + 5.0) * 0.9,
            'last_price': max(0, strike - underlying_price + 5.0) * 0.85,
            'volume': 100,
            'open_interest': 500
        })

    option_chain = pd.DataFrame(sample_data)

    # Create sample market data with some upward trend to get bullish signal
    dates = [datetime.now() - timedelta(days=i) for i in range(50, 0, -1)]  # 50 days of data
    prices = [140 + i * 0.5 for i in range(50)]  # Upward trend from 140 to 165

    market_data = pd.DataFrame({
        'date': dates,
        'adjusted_close': prices,
        'volume': [1000000] * 50
    })

    return option_chain, market_data

def test_protective_put_strategy():
    """Test the protective put strategy with debugging."""
    print("=== Debugging Protective Put Strategy ===")

    # Create strategy
    pp_strategy = ProtectivePutStrategy('AAPL')

    # Create sample data
    option_chain, market_data = create_sample_data()

    print(f"Market data shape: {market_data.shape}")
    print(f"Market data head:\n{market_data.head()}")
    print(f"Underlying price: {market_data['adjusted_close'].iloc[-1]}")

    # Test signal generator directly
    signal_gen = SignalGenerator()
    underlying_signal = signal_gen.get_signal(market_data, datetime.now())
    print(f"Underlying signal: {underlying_signal}")

    # Create sample data
    option_chain, market_data = create_sample_data()

    # Debug signal generation step by step
    current_date = datetime.now()

    # Get underlying signal
    underlying_signal = pp_strategy.get_underlying_signal(market_data, current_date)
    print(f"Underlying signal: {underlying_signal}")
    if underlying_signal is None:
        return

    # Get underlying price
    underlying_price = pp_strategy._get_underlying_price(market_data, current_date)
    print(f"Underlying price: {underlying_price}")
    if underlying_price is None:
        return

    # Filter option chain for puts with appropriate DTE
    puts = option_chain[
        (option_chain['option_type'] == 'put') &
        option_chain['expiration_date'].notna()
    ].copy()

    print(f"Total puts found: {len(puts)}")
    if puts.empty:
        print("No put options found in chain")
        return

    # Calculate days to expiration
    puts['days_to_exp'] = puts['expiration_date'].apply(
        lambda x: (datetime.strptime(x, '%Y-%m-%d') - current_date).days
    )

    print(f"Put DTE range: {puts['days_to_exp'].min()} to {puts['days_to_exp'].max()}")
    print(f"Preferred DTE: {pp_strategy.preferred_dte}")

    # Filter to preferred DTE and future expirations
    puts = puts[
        puts['days_to_exp'].isin(pp_strategy.preferred_dte) &
        (puts['days_to_exp'] > 0)
    ]

    print(f"Puts after DTE filter: {len(puts)}")
    if puts.empty:
        print(f"No puts found in preferred DTE range: {pp_strategy.preferred_dte}")
        return

    # Calculate moneyness for each put: (strike - spot) / spot
    puts['moneyness'] = (puts['strike_price'] - underlying_price) / underlying_price

    print(f"Put moneyness range: {puts['moneyness'].min():.3f} to {puts['moneyness'].max():.3f}")
    print(f"Preferred moneyness: {pp_strategy.preferred_moneyness}")

    # Filter to preferred moneyness range (ATM puts)
    min_otm, max_otm = pp_strategy.preferred_moneyness
    puts = puts[
        (puts['moneyness'] >= min_otm) &
        (puts['moneyness'] <= max_otm)
    ]

    print(f"Puts after moneyness filter: {len(puts)}")
    if puts.empty:
        print(f"No puts found in preferred moneyness range: {pp_strategy.preferred_moneyness}")
        return

    # For each preferred DTE, select best put
    for dte in pp_strategy.preferred_dte:
        dte_puts = puts[puts['days_to_exp'] == dte].copy()
        print(f"DTE {dte}: {len(dte_puts)} puts")

        if dte_puts.empty:
            continue

        # Select the put with highest premium
        dte_puts['mid_price'] = dte_puts.apply(
            lambda row: ((row.get('bid_price', 0) + row.get('ask_price', 0)) / 2
                       if row.get('bid_price') is not None and row.get('ask_price') is not None
                       else row.get('last_price', 0)),
            axis=1
        )

        best_put = dte_puts.loc[dte_puts['mid_price'].idxmax()]
        print(f"Best put for DTE {dte}: strike={best_put['strike_price']}, mid_price={best_put['mid_price']}")

        # Create signal
        signal = {
            'underlying_symbol': pp_strategy.underlying_symbol,
            'signal_type': 'protective_put',
            'signal_strength': underlying_signal['signal_strength'],
            'underlying_price': underlying_price,
            'put_strike': best_put['strike_price'],
            'put_expiration': best_put['expiration_date'],
            'put_symbol': best_put['option_symbol'],
            'days_to_exp': int(best_put['days_to_exp']),
            'put_mid_price': best_put['mid_price'],
            'timestamp': current_date,
            'underlying_signal': underlying_signal
        }

        print(f"Generated signal: {signal}")
        return  # Just return first signal for debugging

    print("No signals generated")

if __name__ == "__main__":
    test_protective_put_strategy()
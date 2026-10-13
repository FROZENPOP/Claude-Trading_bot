#!/usr/bin/env python3
"""Test script for protective put strategy."""

import sys
import os
sys.path.insert(0, '.')

import pandas as pd
from datetime import datetime, timedelta

from trading_bot.strategies.protective_put import ProtectivePutStrategy

def create_sample_data():
    """Create sample option chain and market data for testing."""
    # Create sample option chain data
    sample_data = []
    base_date = datetime.now() + timedelta(days=46)  # Use 46 days to get 45 DTE
    exp_date = base_date.strftime('%Y-%m-%d')

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

    # Create sample market data
    market_data = pd.DataFrame({
        'date': [datetime.now() - timedelta(days=i) for i in range(50, 0, -1)],  # 50 days of data
        'adjusted_close': [148 + i * 0.3 for i in range(50)],  # Upward trend from 148 to 163
        'volume': [1000000] * 50
    })

    return option_chain, market_data

def test_protective_put_strategy():
    """Test the protective put strategy."""
    print("=== Testing Protective Put Strategy ===")

    # Create strategy
    pp_strategy = ProtectivePutStrategy('AAPL')

    # Create sample data
    option_chain, market_data = create_sample_data()

    # Generate signals
    pp_signals = pp_strategy.generate_protective_put_signals(market_data, option_chain)
    print(f"Generated {len(pp_signals)} protective put signals")

    if pp_signals:
        signal = pp_signals[0]
        print(f"Signal: {signal}")

        # Create position
        position = pp_strategy.create_protective_put_position(signal, portfolio_value=200000)  # Increased portfolio value
        if position:
            print(f"Created position: {position}")

            # Check exit condition
            should_exit, exit_value, reason = pp_strategy.exit_protective_put(
                position, market_data, option_chain, datetime.now()
            )
            print(f"Exit recommendation: {should_exit} - {reason}")

            # Test expiration calculation
            exp_date = datetime.strptime(position.put_expiration, '%Y-%m-%d')
            should_exit_exp, exp_value, reason_exp = pp_strategy._calculate_protective_put_expiration(
                position, exp_date, market_data
            )
            print(f"Expiration test: {should_exit_exp} - {reason_exp} - Value: ${exp_value:.2f}")
        else:
            print("Failed to create position")
    else:
        print("No signals generated")

    print("Test completed!")

if __name__ == "__main__":
    test_protective_put_strategy()
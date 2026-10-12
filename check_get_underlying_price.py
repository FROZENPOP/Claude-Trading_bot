#!/usr/bin/env python3
"""Check the _get_underlying_price method."""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
import inspect

# Add project to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy

def get_underlying_price_source():
    """Get the source of _get_underlying_price."""
    print("SOURCE OF _get_underlying_price METHOD")
    print("=" * 40)

    strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)

    try:
        source = inspect.getsource(strategy._get_underlying_price)
        print(source)
    except Exception as e:
        print(f"Could not get source: {e}")

def test_get_underlying_price():
    """Test the _get_underlying_price method with correct vs incorrect params."""
    print("\n" + "=" * 40)
    print("TESTING _get_underlying_price METHOD")
    print("=" * 40)

    from research_options_strategies import OptionsDataPipeline

    # Create test data
    pipeline = OptionsDataPipeline(symbol="AAPL")
    lookback_start = "2026-07-19"
    end_date = "2026-09-07"

    stock_data = pipeline.get_stock_data(lookback_start, end_date)
    current_date = stock_data['date'].iloc[-1]
    available_data = stock_data[stock_data['date'] <= current_date].copy()

    print(f"Test data: {len(available_data)} rows from {available_data['date'].min()} to {available_data['date'].max()}")
    print(f"Current date: {current_date}")
    print(f"Available close prices: {available_data['close'].tail(3).tolist()}")

    strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)

    # Test with market_data=None (the buggy call)
    print(f"\nTesting with market_data=None (current buggy call):")
    price_none = strategy._get_underlying_price(market_data=None, current_date=current_date)
    print(f"  Result: {price_none}")

    # Test with market_data=available_data (correct call)
    print(f"\nTesting with market_data=available_data (correct call):")
    price_correct = strategy._get_underlying_price(market_data=available_data, current_date=current_date)
    print(f"  Result: {price_correct}")

    # Show what the data looks like
    if price_correct is not None:
        actual_close = available_data['close'].iloc[-1]
        print(f"\nValidation:")
        print(f"  Actual close price: {actual_close}")
        print(f"  Returned price: {price_correct}")
        print(f"  Match: {abs(price_correct - actual_close) < 0.01}")

def main():
    """Main function."""
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    get_underlying_price_source()
    test_get_underlying_price()

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
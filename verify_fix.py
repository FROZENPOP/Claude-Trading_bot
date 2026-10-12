#!/usr/bin/env python3
"""Simple verification that the fix works correctly."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add project to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

# Import the OptionsDataPipeline from the research script
from research_options_strategies import OptionsDataPipeline

def test_options_datapipeline():
    """Test the OptionsDataPipeline to see what columns it provides."""

    print("Testing OptionsDataPipeline.get_stock_data from research script (after fix)...")

    pipeline = OptionsDataPipeline(symbol="AAPL")

    # Get stock data for a recent period
    stock_data = pipeline.get_stock_data("2026-04-01", "2026-04-30")

    print(f"Stock data shape: {stock_data.shape}")
    print(f"Stock data columns: {list(stock_data.columns)}")
    print(f"Has 'adjusted_close': {'adjusted_close' in stock_data.columns}")
    print(f"Has 'close': {'close' in stock_data.columns}")

    if not stock_data.empty:
        print("\nFirst few rows:")
        print(stock_data.head())

        # Test what happens when signal generator tries to access adjusted_close
        print("\nTesting signal generator access...")
        try:
            # This is what the signal generator tries to do
            adjusted_close_series = stock_data['adjusted_close']
            print("SUCCESS: Able to access 'adjusted_close' column")
            print(f"adjusted_close values: {adjusted_close_series.tolist()[:5]}...")

            # Also verify it equals close (as we set it)
            close_series = stock_data['close']
            if (adjusted_close_series == close_series).all():
                print("CONFIRMED: adjusted_close equals close (as expected for research simulation)")
                return True
            else:
                print("WARNING: adjusted_close does not equal close")
                return False

        except KeyError as e:
            print(f"ERROR: KeyError when accessing 'adjusted_close': {e}")
            print("This indicates the fix did not work!")
            return False
    else:
        print("No data returned!")
        return False

if __name__ == "__main__":
    success = test_options_datapipeline()
    if success:
        print("\nFIX VERIFICATION PASSED")
    else:
        print("\nFIX VERIFICATION FAILED")
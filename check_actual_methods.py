#!/usr/bin/env python3
"""Check the actual _generate_bear_put_signals and _generate_bull_call_signals methods."""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
import inspect

# Add project to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy

def check_method_source():
    """Check the source of the signal generation methods."""
    print("VERTICAL SPREAD STRATEGY METHODS")
    print("=" * 40)

    strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)

    # Check _generate_bear_put_signals
    print("_generate_bear_put_signals METHOD:")
    print("-" * 40)
    try:
        source = inspect.getsource(strategy._generate_bear_put_signals)
        print(source)
    except Exception as e:
        print(f"Could not get source: {e}")

    print("\n" + "=" * 40)
    print("_generate_bull_call_signals METHOD:")
    print("-" * 40)
    try:
        source = inspect.getsource(strategy._generate_bull_call_signals)
        print(source)
    except Exception as e:
        print(f"Could not get source: {e}")

if __name__ == "__main__":
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    check_method_source()
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
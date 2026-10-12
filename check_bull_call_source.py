#!/usr/bin/env python3
"""Check the _generate_bull_call_signals method for the same bug."""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
import inspect

# Add project to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy

def get_bull_call_source():
    """Get the source of _generate_bull_call_signals."""
    print("SOURCE OF _generate_bull_call_signals METHOD")
    print("=" * 50)

    strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)

    try:
        source = inspect.getsource(strategy._generate_bull_call_signals)
        print(source)
    except Exception as e:
        print(f"Could not get source: {e}")

def main():
    """Main function."""
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    get_bull_call_source()

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
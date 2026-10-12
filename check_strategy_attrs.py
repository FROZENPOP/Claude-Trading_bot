#!/usr/bin/env python3
"""Check what attributes the VerticalSpreadStrategy has."""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

# Add project to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy

def check_attributes():
    """Check the attributes of VerticalSpreadStrategy."""
    print("VERTICAL SPREAD STRATEGY ATTRIBUTES")
    print("=" * 40)

    strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)

    # Get all attributes
    attrs = [attr for attr in dir(strategy) if not attr.startswith('_')]
    print("Public attributes:")
    for attr in sorted(attrs):
        if not callable(getattr(strategy, attr)):
            print(f"  {attr}: {getattr(strategy, attr)}")

    # Check for OTM percentages specifically
    print("\nChecking for OTM-related attributes:")
    for attr in ['put_otm_percentage', 'call_otm_percentage', 'otm_percentage']:
        if hasattr(strategy, attr):
            print(f"  {attr}: {getattr(strategy, attr)}")
        else:
            print(f"  {attr}: NOT FOUND")

    # Let's look at the actual source to see how it calculates strikes
    import inspect
    try:
        source = inspect.getsource(strategy.__init__)
        print("\n__init__ method:")
        print(source)
    except Exception as e:
        print(f"Could not get __init__ source: {e}")

if __name__ == "__main__":
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    check_attributes()
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
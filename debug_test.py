#!/usr/bin/env python3
import sys
import os
import traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from trading_bot.backtesting.enhanced_robustness_fixed import EnhancedWalkForwardAnalyzer
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Create minimal test data
dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
data = pd.DataFrame({
    'date': dates,
    'open': np.random.rand(100) * 100,
    'high': np.random.rand(100) * 100,
    'low': np.random.rand(100) * 100,
    'close': np.random.rand(100) * 100,
    'volume': np.random.randint(1000, 10000, 100),
    'adjusted_close': np.random.rand(100) * 100
})

# Simple test config
test_configs = [
    {'name': 'test_config', 'strategy_type': 'trend_following', 'fast_period': 10, 'slow_period': 30, 'signal_threshold': 0.02}
]

# Simple selector
def selector(results):
    return results[0] if results else None

# Create analyzer
analyzer = EnhancedWalkForwardAnalyzer(
    data=data,
    symbol='TEST',
    initial_capital=100000,
    window_size=50,
    step_size=25,
    optimal_config_selector=selector
)

# Run analysis with error handling
try:
    print("Running analysis...")
    results = analyzer.run_analysis(
        configs=test_configs,
        verbose=True
    )
    print(f"Results type: {type(results)}")
    print(f"Results: {results}")
    if results is not None:
        print(f"Results length: {len(results)}")
        if results:
            print(f"First result IS return: {results[0].in_sample_return}")
            print(f"First result OOS return: {results[0].out_of_sample_return}")
    else:
        print("Results is None!")
except Exception as e:
    print(f"Exception occurred: {e}")
    traceback.print_exc()
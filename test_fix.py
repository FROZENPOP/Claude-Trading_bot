#!/usr/bin/env python3
import sys
import os
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

# Simple test config using only existing strategies
test_configs = [
    {'name': 'test_config', 'strategy_type': 'trend_following',
     'entry_threshold': 0.5, 'exit_threshold': -0.3,
     'short_window': 10, 'medium_window': 20, 'long_window': 30}
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
    print(f"Results length: {len(results)}")
    if results is not None and len(results) > 0:
        print(f"First result IS return: {results[0].in_sample_return}")
        print(f"First result OOS return: {results[0].out_of_sample_return}")
        print(f"First result IS max_dd: {results[0].in_sample_max_dd}")
        print(f"First result OOS max_dd: {results[0].out_of_sample_max_dd}")
        print("SUCCESS: No TypeError occurred!")
    else:
        print("Results is None or empty!")
except Exception as e:
    print(f"Exception occurred: {e}")
    import traceback
    traceback.print_exc()